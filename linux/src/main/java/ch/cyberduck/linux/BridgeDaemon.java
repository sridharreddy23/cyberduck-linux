/*
 * Copyright (c) 2002-2026 iterate GmbH. All rights reserved.
 * https://cyberduck.io/
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
package ch.cyberduck.linux;

import ch.cyberduck.core.*;
import ch.cyberduck.core.exception.BackgroundException;
import ch.cyberduck.core.pool.SessionPool;
import ch.cyberduck.core.preferences.PreferencesFactory;
import ch.cyberduck.core.serviceloader.AutoServiceLoaderFactory;
import ch.cyberduck.core.threading.MainAction;
import ch.cyberduck.core.threading.WorkerBackgroundAction;
import ch.cyberduck.core.transfer.DownloadTransfer;
import ch.cyberduck.core.transfer.Transfer;
import ch.cyberduck.core.transfer.TransferOptions;
import ch.cyberduck.core.transfer.TransferProgress;
import ch.cyberduck.core.transfer.TransferQueueFactory;
import ch.cyberduck.core.transfer.UploadTransfer;
import ch.cyberduck.core.worker.CreateDirectoryWorker;
import ch.cyberduck.core.worker.DeleteWorker;
import ch.cyberduck.core.worker.ListWorker;
import ch.cyberduck.core.worker.MountWorker;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import ch.cyberduck.core.threading.NamedThreadFactory;
import ch.cyberduck.core.exception.LoginCanceledException;

/**
 * Headless JSON-RPC daemon for driving the Cyberduck core engine from Python or other frontends.
 * Communicates via JSON lines over standard I/O.
 */
public final class BridgeDaemon {

    private static final Gson GSON = new Gson();
    private static DaemonController controller;
    private static SessionPool pool = SessionPool.DISCONNECTED;
    private static PathCache cache;
    private static Path currentWorkdir;
    private static final Map<String, CompletableFuture<Credentials>> PENDING_PROMPTS = new ConcurrentHashMap<>();
    private static final AtomicLong PROMPT_ID_GEN = new AtomicLong();
    private static final ExecutorService EXECUTOR = Executors.newCachedThreadPool(new NamedThreadFactory("bridge-command"));

    public static final class DaemonHostKeyCallback implements HostKeyCallback {
        public DaemonHostKeyCallback() {}
        public DaemonHostKeyCallback(final Controller controller) {}
        @Override
        public boolean verify(final Host host, final java.security.PublicKey key) {
            return true;
        }
    }

    public static final class DaemonLoginCallback extends DisabledLoginCallback {
        public DaemonLoginCallback() {}
        public DaemonLoginCallback(final Controller controller) {}

        @Override
        public Credentials prompt(final Host bookmark, final String username, final String title, final String reason, final LoginOptions options) throws LoginCanceledException {
            final String promptId = "prompt-" + PROMPT_ID_GEN.incrementAndGet();
            final CompletableFuture<Credentials> future = new CompletableFuture<>();
            PENDING_PROMPTS.put(promptId, future);

            final JsonObject evt = new JsonObject();
            evt.addProperty("event", "promptCredentials");
            evt.addProperty("promptId", promptId);
            evt.addProperty("title", title != null ? title : "Login Required");
            evt.addProperty("reason", reason != null ? reason : "");
            final String user = username != null ? username : (bookmark.getCredentials() != null ? bookmark.getCredentials().getUsername() : "");
            evt.addProperty("username", user != null ? user : "");
            evt.addProperty("hostname", bookmark.getHostname());
            sendResponse(evt);

            try {
                final Credentials result = future.get(120, TimeUnit.SECONDS);
                if(result == null) {
                    throw new LoginCanceledException(new Exception("Login canceled by user."));
                }
                return result;
            }
            catch(final TimeoutException e) {
                throw new LoginCanceledException(new Exception("Login prompt timed out."));
            }
            catch(final ExecutionException e) {
                if(e.getCause() instanceof LoginCanceledException lce) {
                    throw lce;
                }
                throw new LoginCanceledException(e.getCause() != null ? e.getCause() : new Exception(e.getMessage()));
            }
            catch(final InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new LoginCanceledException(new Exception("Interrupted."));
            }
            finally {
                PENDING_PROMPTS.remove(promptId);
            }
        }
    }

    public static final class DaemonPasswordCallback implements PasswordCallback {
        public DaemonPasswordCallback() {}
        public DaemonPasswordCallback(final Controller controller) {}
        @Override
        public Credentials prompt(final Host host, final String title, final String message, final LoginOptions options) throws LoginCanceledException {
            if(host.getCredentials() != null && host.getCredentials().getPassword() != null && !host.getCredentials().getPassword().isEmpty()) {
                return host.getCredentials();
            }
            return new DaemonLoginCallback().prompt(host, host.getCredentials() != null ? host.getCredentials().getUsername() : null, title, message, options);
        }
        @Override
        public void close(final String input) {
        }
    }

    public static final class DaemonCertificateTrustCallback implements CertificateTrustCallback {
        public DaemonCertificateTrustCallback() {}
        public DaemonCertificateTrustCallback(final Controller controller) {}
        @Override
        public void prompt(final String title, final java.util.List<java.security.cert.X509Certificate> certificates) {
        }
    }

    public static final class DaemonAlertCallback implements ch.cyberduck.core.threading.AlertCallback {
        public DaemonAlertCallback() {}
        public DaemonAlertCallback(final Controller controller) {}
        @Override
        public boolean alert(final Host host, final BackgroundException failure) {
            return false;
        }
    }

    public static final class DaemonPreferences extends ch.cyberduck.core.preferences.MemoryPreferences {
        @Override
        protected void setDefaults() {
            super.setDefaults();
            this.setDefault("local.user.home", System.getProperty("user.home"));
            this.setDefault("connection.login.name", System.getProperty("user.name"));
            this.setDefault("logging", "fatal");
            this.setDefault("profiles.folder.name", "profiles");
            // Keep local download time as file modification time so downloaded files
            // appear at the top of the Downloads folder in file managers (Nautilus/Explorer)
            this.setDefault("queue.download.timestamp.change", "false");
        }

        @Override
        protected void setFactories() {
            super.setFactories();
            this.setDefault("factory.applicationresourcesfinder.class", LinuxResourcesFinder.class.getName());
            this.setDefault("factory.supportdirectoryfinder.class", ch.cyberduck.core.preferences.UserHomeSupportDirectoryFinder.class.getName());
            this.setDefault("factory.localsupportdirectoryfinder.class", ch.cyberduck.core.preferences.UserHomeSupportDirectoryFinder.class.getName());
            this.setDefault("factory.locale.class", ch.cyberduck.core.i18n.RegexLocale.class.getName());
            this.setDefault("factory.applicationlauncher.class", ch.cyberduck.core.local.ExecApplicationLauncher.class.getName());
            this.setDefault("factory.editorfactory.class", ch.cyberduck.core.editor.DefaultEditorFactory.class.getName());
            this.setDefault("factory.proxy.class", ch.cyberduck.core.proxy.EnvironmentVariableProxyFinder.class.getName());
            this.setDefault("factory.symlink.class", ch.cyberduck.core.local.DefaultSymlinkFeature.class.getName());
            this.setDefault("factory.passwordstore.class", ch.cyberduck.core.UnsecureHostPasswordStore.class.getName());
            this.setDefault("factory.browserlauncher.class", XdgBrowserLauncher.class.getName());
            this.setDefault("factory.hostkeycallback.class", DaemonHostKeyCallback.class.getName());
            this.setDefault("factory.logincallback.class", DaemonLoginCallback.class.getName());
            this.setDefault("factory.passwordcallback.class", DaemonPasswordCallback.class.getName());
            this.setDefault("factory.certificatetrustcallback.class", DaemonCertificateTrustCallback.class.getName());
            this.setDefault("factory.alertcallback.class", DaemonAlertCallback.class.getName());
            for(Transfer.Type type : Transfer.Type.values()) {
                this.setDefault(String.format("factory.transferpromptcallback.%s.class", type.name()), ch.cyberduck.core.transfer.DisabledTransferPrompt.class.getName());
            }
        }
    }

    private static final class DaemonController extends AbstractController {
        @Override
        public void invoke(final MainAction runnable, final boolean wait) {
            runnable.run();
        }

        @Override
        public void message(final String message) {
            super.message(message);
            if(message != null && !message.isEmpty()) {
                sendEvent("status", "message", message);
            }
        }
    }

    public static synchronized void sendResponse(final JsonObject obj) {
        System.out.println(GSON.toJson(obj));
        System.out.flush();
    }

    public static synchronized void sendEvent(final String event, final String key, final Object value) {
        final JsonObject obj = new JsonObject();
        obj.addProperty("event", event);
        if(value instanceof Number) {
            obj.addProperty(key, (Number) value);
        }
        else if(value instanceof Boolean) {
            obj.addProperty(key, (Boolean) value);
        }
        else {
            obj.addProperty(key, String.valueOf(value));
        }
        System.out.println(GSON.toJson(obj));
        System.out.flush();
    }

    public static void main(final String[] args) {
        System.setProperty("java.awt.headless", "true");
        Thread.currentThread().setContextClassLoader(BridgeDaemon.class.getClassLoader());

        PreferencesFactory.set(new DaemonPreferences());
        controller = new DaemonController();
        cache = new PathCache(PreferencesFactory.get().getInteger("browser.cache.size"));

        final ProtocolFactory protocols = ProtocolFactory.get();
        try {
            protocols.register(new ch.cyberduck.core.sftp.SFTPProtocol());
            protocols.register(new ch.cyberduck.core.ftp.FTPProtocol());
            protocols.register(new ch.cyberduck.core.dav.DAVProtocol());
            protocols.register(new ch.cyberduck.core.s3.S3Protocol());
        }
        catch(final Throwable t) {
            // ignore if not on classpath
        }

        try {
            for(final Protocol p : AutoServiceLoaderFactory.<Protocol>get().load(Protocol.class)) {
                protocols.register(p);
            }
        }
        catch(final Throwable t) {
            // ignore
        }

        try {
            protocols.load();
        }
        catch(final Throwable t) {
            // ignore
        }

        sendEvent("ready", "version", "9.6.1");

        final BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        try {
            while((line = reader.readLine()) != null) {
                line = line.trim();
                if(line.isEmpty()) {
                    continue;
                }
                try {
                    final JsonObject req = JsonParser.parseString(line).getAsJsonObject();
                    handleRequest(req);
                }
                catch(final Throwable e) {
                    final JsonObject err = new JsonObject();
                    err.addProperty("status", "error");
                    err.addProperty("error", e.getMessage() == null ? e.toString() : e.getMessage());
                    sendResponse(err);
                }
            }
        }
        catch(final Exception e) {
            // System.in closed
        }
        finally {
            if(pool != SessionPool.DISCONNECTED) {
                try {
                    pool.shutdown();
                }
                catch(final Exception ignored) {
                }
            }
        }
    }

    private static void handleRequest(final JsonObject req) {
        final String cmd = req.has("cmd") ? req.get("cmd").getAsString() : "";
        final String id = req.has("id") ? req.get("id").getAsString() : null;

        if("credentialsResponse".equals(cmd)) {
            final String promptId = req.has("promptId") ? req.get("promptId").getAsString() : null;
            final boolean canceled = req.has("canceled") && req.get("canceled").getAsBoolean();
            if(promptId != null) {
                final CompletableFuture<Credentials> future = PENDING_PROMPTS.remove(promptId);
                if(future != null) {
                    if(canceled) {
                        future.completeExceptionally(new LoginCanceledException(new Exception("Login canceled by user.")));
                    }
                    else {
                        final String user = req.has("username") ? req.get("username").getAsString() : "";
                        final String pass = req.has("password") ? req.get("password").getAsString() : "";
                        final String token = req.has("token") && !req.get("token").isJsonNull() ? req.get("token").getAsString() : null;
                        final Credentials creds = new Credentials(user, pass);
                        if(token != null && !token.isEmpty()) {
                            creds.setTokens(new TemporaryAccessTokens(user, pass, token));
                        }
                        future.complete(creds);
                    }
                }
            }
            return;
        }

        EXECUTOR.submit(() -> {
            try {
                handleRequestAsync(req);
            }
            catch(final Throwable e) {
                final JsonObject err = new JsonObject();
                if(id != null) {
                    err.addProperty("id", id);
                }
                err.addProperty("status", "error");
                err.addProperty("error", e.getMessage() == null ? e.toString() : e.getMessage());
                sendResponse(err);
            }
        });
    }

    private static void handleRequestAsync(final JsonObject req) {
        final String cmd = req.has("cmd") ? req.get("cmd").getAsString() : "";
        final String id = req.has("id") ? req.get("id").getAsString() : null;

        final JsonObject res = new JsonObject();
        if(id != null) {
            res.addProperty("id", id);
        }

        switch(cmd) {
            case "ping" -> {
                res.addProperty("status", "ok");
                res.addProperty("message", "pong");
                sendResponse(res);
            }
            case "protocols" -> {
                res.addProperty("status", "ok");
                final JsonArray array = new JsonArray();
                final List<Protocol> list = ProtocolChoice.choices();
                for(final Protocol p : list) {
                    final JsonObject item = new JsonObject();
                    item.addProperty("id", p.getIdentifier());
                    item.addProperty("prefix", p.getPrefix());
                    item.addProperty("name", p.getName());
                    item.addProperty("description", p.getDescription());
                    item.addProperty("scheme", p.getScheme().name());
                    item.addProperty("defaultPort", p.getDefaultPort());
                    array.add(item);
                }
                res.add("protocols", array);
                sendResponse(res);
            }
            case "connect" -> handleConnect(req, res);
            case "disconnect" -> {
                if(pool != SessionPool.DISCONNECTED) {
                    final SessionPool closing = pool;
                    pool = SessionPool.DISCONNECTED;
                    currentWorkdir = null;
                    cache.clear();
                    new Thread(closing::shutdown, "cyberduck-disconnect").start();
                }
                res.addProperty("status", "ok");
                sendResponse(res);
            }
            case "list" -> handleList(req, res);
            case "mkdir" -> handleMkdir(req, res);
            case "delete" -> handleDelete(req, res);
            case "download" -> handleDownload(req, res);
            case "upload" -> handleUpload(req, res);
            default -> {
                res.addProperty("status", "error");
                res.addProperty("error", "Unknown command: " + cmd);
                sendResponse(res);
            }
        }
    }

    private static String formatError(final BackgroundException failure) {
        if(failure == null) {
            return "Connection failed.";
        }
        for(final Throwable t : failure.getSuppressed()) {
            if(t instanceof BackgroundException be) {
                final String d = be.getDetail();
                if(d != null && !d.isBlank()) {
                    return be.getMessage() != null ? be.getMessage() + ": " + d : d;
                }
                if(be.getMessage() != null && !be.getMessage().isBlank()) {
                    return be.getMessage();
                }
            }
        }
        String msg = failure.getMessage();
        final String detail = failure.getDetail();
        if(detail != null && !detail.isBlank()) {
            msg = (msg != null && !msg.isBlank() && !msg.equalsIgnoreCase("Unknown")) ? msg + ". " + detail : detail;
        }
        if(msg == null || msg.isBlank() || msg.equalsIgnoreCase("Unknown")) {
            if(failure.getCause() != null && failure.getCause().getMessage() != null && !failure.getCause().getMessage().isBlank()) {
                msg = failure.getCause().getMessage();
            }
            else if(failure instanceof LoginCanceledException) {
                msg = "Login canceled or authentication failed (password required).";
            }
            else {
                msg = failure.toString();
            }
        }
        return msg;
    }

    private static void handleConnect(final JsonObject req, final JsonObject res) {
        try {
            final String protocolId = req.get("protocol").getAsString();
            final String hostname = req.get("hostname").getAsString();
            final int port = req.has("port") ? req.get("port").getAsInt() : 22;
            final String username = req.has("username") ? req.get("username").getAsString() : System.getProperty("user.name");
            final String password = req.has("password") && !req.get("password").isJsonNull() ? req.get("password").getAsString() : null;
            final String token = req.has("token") && !req.get("token").isJsonNull() ? req.get("token").getAsString() : null;
            final String identity = req.has("identity") && !req.get("identity").isJsonNull() ? req.get("identity").getAsString() : null;

            Protocol protocol = ProtocolFactory.get().forName(protocolId);
            if(protocol == null) {
                for(final Protocol p : ProtocolChoice.choices()) {
                    if(protocolId.equalsIgnoreCase(p.getIdentifier()) || protocolId.equalsIgnoreCase(p.getPrefix()) || protocolId.equalsIgnoreCase(p.getScheme().name())) {
                        protocol = p;
                        break;
                    }
                }
            }
            if(protocol == null) {
                protocol = new ch.cyberduck.core.sftp.SFTPProtocol();
            }

            final Credentials credentials = new Credentials(username, password);
            if(token != null && !token.isEmpty()) {
                credentials.setTokens(new TemporaryAccessTokens(username, password, token));
            }
            if(identity != null && !identity.isEmpty()) {
                credentials.setIdentity(LocalFactory.get(identity));
            }

            final Host host = new Host(protocol, hostname, port, credentials);
            if(pool != SessionPool.DISCONNECTED) {
                pool.shutdown();
            }

            cache = new PathCache(PreferencesFactory.get().getInteger("browser.cache.size"));
            final SessionPool next = SessionPoolFactory.create(controller, host, SessionPoolFactory.Usage.browser);
            pool = next;

            final CountDownLatch latch = new CountDownLatch(1);
            final AtomicReference<Path> rootRef = new AtomicReference<>();
            final AtomicReference<BackgroundException> errorRef = new AtomicReference<>();

            controller.background(new WorkerBackgroundAction<Path>(controller, next,
                    new MountWorker(host, cache, new DisabledListProgressListener())) {
                @Override
                public void cleanup(final Path result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    rootRef.set(result);
                    errorRef.set(failure);
                    latch.countDown();
                }
            });

            latch.await();

            if(errorRef.get() != null) {
                pool = SessionPool.DISCONNECTED;
                res.addProperty("status", "error");
                res.addProperty("error", formatError(errorRef.get()));
            }
            else {
                currentWorkdir = rootRef.get();
                res.addProperty("status", "ok");
                res.addProperty("workdir", currentWorkdir.getAbsolute());
                res.addProperty("hostname", hostname);
            }
        }
        catch(final Throwable t) {
            pool = SessionPool.DISCONNECTED;
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
        }
        sendResponse(res);
    }

    private static void handleList(final JsonObject req, final JsonObject res) {
        if(pool == SessionPool.DISCONNECTED) {
            res.addProperty("status", "error");
            res.addProperty("error", "Not connected");
            sendResponse(res);
            return;
        }

        try {
            final String pathStr = req.has("path") ? req.get("path").getAsString() : (currentWorkdir != null ? currentWorkdir.getAbsolute() : "/");
            final Path dir = new Path(pathStr, EnumSet.of(Path.Type.directory));

            final CountDownLatch latch = new CountDownLatch(1);
            final AtomicReference<AttributedList<Path>> listRef = new AtomicReference<>();
            final AtomicReference<BackgroundException> errorRef = new AtomicReference<>();

            controller.background(new WorkerBackgroundAction<AttributedList<Path>>(controller, pool,
                    new ListWorker(cache, dir, new DisabledListProgressListener())) {
                @Override
                public void cleanup(final AttributedList<Path> result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    listRef.set(result);
                    errorRef.set(failure);
                    latch.countDown();
                }
            });

            latch.await();

            if(errorRef.get() != null) {
                res.addProperty("status", "error");
                res.addProperty("error", formatError(errorRef.get()));
            }
            else {
                currentWorkdir = dir;
                final AttributedList<Path> listing = listRef.get();
                final JsonArray array = new JsonArray();
                if(listing != null) {
                    for(final Path p : listing) {
                        final JsonObject item = new JsonObject();
                        item.addProperty("name", p.getName());
                        item.addProperty("absolute", p.getAbsolute());
                        item.addProperty("isDir", p.isDirectory());
                        item.addProperty("isSymlink", p.isSymbolicLink());
                        final PathAttributes attr = p.attributes();
                        item.addProperty("size", attr.getSize());
                        item.addProperty("modified", attr.getModificationDate());
                        final Permission perm = attr.getPermission();
                        item.addProperty("permission", perm != null ? perm.toString() : "");
                        array.add(item);
                    }
                }
                res.addProperty("status", "ok");
                res.addProperty("path", dir.getAbsolute());
                res.add("files", array);
            }
        }
        catch(final Throwable t) {
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
        }
        sendResponse(res);
    }

    private static void handleMkdir(final JsonObject req, final JsonObject res) {
        if(pool == SessionPool.DISCONNECTED || currentWorkdir == null) {
            res.addProperty("status", "error");
            res.addProperty("error", "Not connected");
            sendResponse(res);
            return;
        }

        try {
            final String name = req.get("name").getAsString();
            final Path folder = new Path(currentWorkdir, name, EnumSet.of(Path.Type.directory));

            final CountDownLatch latch = new CountDownLatch(1);
            final AtomicReference<BackgroundException> errorRef = new AtomicReference<>();

            controller.background(new WorkerBackgroundAction<Path>(controller, pool,
                    new CreateDirectoryWorker(folder, pool.getHost().getRegion())) {
                @Override
                public void cleanup(final Path result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    errorRef.set(failure);
                    latch.countDown();
                }
            });

            latch.await();

            if(errorRef.get() != null) {
                res.addProperty("status", "error");
                res.addProperty("error", formatError(errorRef.get()));
            }
            else {
                cache.invalidate(currentWorkdir);
                res.addProperty("status", "ok");
                res.addProperty("created", folder.getAbsolute());
            }
        }
        catch(final Throwable t) {
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
        }
        sendResponse(res);
    }

    private static void handleDelete(final JsonObject req, final JsonObject res) {
        if(pool == SessionPool.DISCONNECTED || currentWorkdir == null) {
            res.addProperty("status", "error");
            res.addProperty("error", "Not connected");
            sendResponse(res);
            return;
        }

        try {
            final String pathStr = req.get("path").getAsString();
            final boolean isDir = req.has("isDir") && req.get("isDir").getAsBoolean();
            final Path target = new Path(pathStr, isDir ? EnumSet.of(Path.Type.directory) : EnumSet.of(Path.Type.file));

            final CountDownLatch latch = new CountDownLatch(1);
            final AtomicReference<BackgroundException> errorRef = new AtomicReference<>();

            controller.background(new WorkerBackgroundAction<>(controller, pool,
                    new DeleteWorker(LoginCallbackFactory.get(controller), Collections.singletonList(target), controller, cache)) {
                @Override
                public void cleanup(final List<Path> result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    errorRef.set(failure);
                    latch.countDown();
                }
            });

            latch.await();

            if(errorRef.get() != null) {
                res.addProperty("status", "error");
                res.addProperty("error", formatError(errorRef.get()));
            }
            else {
                cache.invalidate(currentWorkdir);
                res.addProperty("status", "ok");
                res.addProperty("deleted", pathStr);
            }
        }
        catch(final Throwable t) {
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
        }
        sendResponse(res);
    }

    private static void handleDownload(final JsonObject req, final JsonObject res) {
        if(pool == SessionPool.DISCONNECTED) {
            res.addProperty("status", "error");
            res.addProperty("error", "Not connected");
            sendResponse(res);
            return;
        }

        try {
            final String remotePath = req.get("remote").getAsString();
            final String localPath = req.get("local").getAsString();
            final String transferId = req.has("transferId") ? req.get("transferId").getAsString() : UUID.randomUUID().toString();

            final Path remote = new Path(remotePath, EnumSet.of(Path.Type.file));
            final Local local = LocalFactory.get(localPath);
            final DownloadTransfer transfer = new DownloadTransfer(pool.getHost(), remote, local).withCache(cache);

            res.addProperty("status", "started");
            res.addProperty("transferId", transferId);
            sendResponse(res);

            startTransferAsync(transferId, transfer);
        }
        catch(final Throwable t) {
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
            sendResponse(res);
        }
    }

    private static void handleUpload(final JsonObject req, final JsonObject res) {
        if(pool == SessionPool.DISCONNECTED || currentWorkdir == null) {
            res.addProperty("status", "error");
            res.addProperty("error", "Not connected");
            sendResponse(res);
            return;
        }

        try {
            final String localPath = req.get("local").getAsString();
            final String remoteName = req.has("name") ? req.get("name").getAsString() : new File(localPath).getName();
            final String transferId = req.has("transferId") ? req.get("transferId").getAsString() : UUID.randomUUID().toString();

            final Local local = LocalFactory.get(localPath);
            final Path remote = new Path(currentWorkdir, remoteName, local.isDirectory() ? EnumSet.of(Path.Type.directory) : EnumSet.of(Path.Type.file));
            final Transfer transfer = new UploadTransfer(pool.getHost(), remote, local).withCache(cache);

            res.addProperty("status", "started");
            res.addProperty("transferId", transferId);
            sendResponse(res);

            startTransferAsync(transferId, transfer);
        }
        catch(final Throwable t) {
            res.addProperty("status", "error");
            res.addProperty("error", t.getMessage() == null ? t.toString() : t.getMessage());
            sendResponse(res);
        }
    }

    private static void startTransferAsync(final String transferId, final Transfer transfer) {
        final boolean useBrowser = Host.TransferType.getType(transfer.getSource()).equals(Host.TransferType.browser);
        final SessionPool source = useBrowser ? pool : SessionPoolFactory.create(controller, transfer.getSource(), controller);
        final SessionPool destination = transfer.getType() == Transfer.Type.copy ? SessionPoolFactory.create(controller, transfer.getDestination(), controller) : SessionPool.DISCONNECTED;

        controller.background(new ch.cyberduck.core.threading.TransferBackgroundAction(controller, source, destination, TransferQueueFactory.get(),
                new ch.cyberduck.core.transfer.TransferAdapter() {
                    @Override
                    public void transferDidProgress(final Transfer t, final TransferProgress status) {
                        final JsonObject ev = new JsonObject();
                        ev.addProperty("event", "transferProgress");
                        ev.addProperty("transferId", transferId);
                        final long size = status.getSize() == null ? 0L : status.getSize();
                        final long transferred = status.getTransferred() == null ? 0L : status.getTransferred();
                        ev.addProperty("size", size);
                        ev.addProperty("transferred", transferred);
                        ev.addProperty("progress", size > 0 ? (double) transferred / size : 0.0);
                        ev.addProperty("text", status.getProgress());
                        sendResponse(ev);
                    }

                    @Override
                    public void transferDidStop(final Transfer t) {
                        final JsonObject ev = new JsonObject();
                        ev.addProperty("event", "transferComplete");
                        ev.addProperty("transferId", transferId);
                        ev.addProperty("complete", t.isComplete());
                        sendResponse(ev);
                        if(currentWorkdir != null) {
                            cache.invalidate(currentWorkdir);
                        }
                    }
                }, controller, transfer, new TransferOptions()) {
            @Override
            public void cleanup(final Boolean result, final BackgroundException failure) {
                super.cleanup(result, failure);
                if(failure != null) {
                    final JsonObject ev = new JsonObject();
                    ev.addProperty("event", "transferFailed");
                    ev.addProperty("transferId", transferId);
                    ev.addProperty("error", failure.getMessage() == null ? failure.toString() : failure.getMessage());
                    sendResponse(ev);
                }
            }
        });
    }
}
