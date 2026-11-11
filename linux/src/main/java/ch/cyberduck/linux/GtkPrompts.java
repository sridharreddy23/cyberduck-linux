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

import ch.cyberduck.core.Controller;
import ch.cyberduck.core.Credentials;
import ch.cyberduck.core.DisabledLoginCallback;
import ch.cyberduck.core.Host;
import ch.cyberduck.core.HostKeyCallback;
import ch.cyberduck.core.Local;
import ch.cyberduck.core.LoginOptions;
import ch.cyberduck.core.PasswordCallback;
import ch.cyberduck.core.TemporaryAccessTokens;
import ch.cyberduck.core.exception.BackgroundException;
import ch.cyberduck.core.exception.ConnectionCanceledException;
import ch.cyberduck.core.exception.LoginCanceledException;

import org.gnome.glib.GLib;
import org.gnome.gtk.Box;
import org.gnome.gtk.Button;
import org.gnome.gtk.Entry;
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.PasswordEntry;
import org.gnome.gtk.Widget;
import org.gnome.gtk.Window;

import java.security.PublicKey;
import java.util.Base64;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Login, certificate-warning and SSH host-key prompts. Called from Cyberduck's background
 * connection thread and marshalled onto the GTK main loop.
 */
public final class GtkPrompts extends DisabledLoginCallback implements HostKeyCallback, PasswordCallback {

    private final Window parent;

    public GtkPrompts(final Controller controller) {
        this(controller instanceof LinuxController ? ((LinuxController) controller).window() : null);
    }

    GtkPrompts(final Window parent) {
        this.parent = parent;
    }

    @Override
    public void close(final String input) {
        // The prompt windows close themselves.
    }

    @Override
    public Credentials prompt(final Host bookmark, final String username, final String title, final String reason,
                              final LoginOptions options) throws LoginCanceledException {
        final Credentials provided = prompt(bookmark, title, reason, options);
        if(username != null && !username.isBlank() && (provided.getUsername() == null || provided.getUsername().isBlank())) {
            provided.setUsername(username);
        }
        return provided;
    }

    @Override
    public Credentials prompt(final Host bookmark, final String title, final String reason, final LoginOptions options) throws LoginCanceledException {
        final AtomicReference<Credentials> result = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        GLib.idleAddOnce(() -> {
            final Window dialog = new Window();
            dialog.setTitle(title == null ? "Login" : title);
            dialog.setModal(true);
            if(parent != null) {
                dialog.setTransientFor(parent);
            }
            dialog.setDefaultSize(520, 20);
            final Box content = new Box(Orientation.VERTICAL, 8);
            content.setMarginStart(16);
            content.setMarginEnd(16);
            content.setMarginTop(16);
            content.setMarginBottom(16);
            if(reason != null && !reason.isBlank()) {
                final Label message = new Label(reason);
                message.setWrap(true);
                message.setXalign(0);
                content.append(message);
            }
            final Entry userEntry = new Entry();
            userEntry.setText(bookmark.getCredentials().getUsername() == null ? "" : bookmark.getCredentials().getUsername());
            final PasswordEntry passwordEntry = new PasswordEntry();
            passwordEntry.setShowPeekIcon(true);
            final String existingPassword = bookmark.getCredentials().getPassword();
            if(existingPassword != null && !existingPassword.isEmpty()) {
                passwordEntry.setText(existingPassword);
            }
            final PasswordEntry tokenEntry = new PasswordEntry();
            tokenEntry.setShowPeekIcon(true);
            final String existingToken = bookmark.getCredentials().getToken();
            if(existingToken != null && !existingToken.isEmpty()) {
                tokenEntry.setText(existingToken);
            }
            final String tokenPlaceholder = bookmark.getProtocol().getTokenPlaceholder();
            final boolean sessionToken = options.token
                    || (options.user && options.password
                    && tokenPlaceholder != null && !tokenPlaceholder.equals(bookmark.getProtocol().getPasswordPlaceholder()));
            final Entry keyEntry = new Entry();
            if(options.user) {
                content.append(row(options.usernamePlaceholder == null || options.usernamePlaceholder.isBlank() ? "Username" : options.usernamePlaceholder, userEntry));
            }
            if(options.password && !options.oauth) {
                content.append(row(options.passwordPlaceholder == null || options.passwordPlaceholder.isBlank() ? "Password" : options.passwordPlaceholder, passwordEntry));
            }
            if(sessionToken) {
                content.append(row(tokenPlaceholder == null || tokenPlaceholder.isBlank() ? "Token" : tokenPlaceholder, tokenEntry));
            }
            if(options.publickey) {
                content.append(row("Private key", keyEntry));
            }
            final Button connect = Button.withLabel(options.oauth ? "Continue" : "Login");
            connect.onClicked(() -> {
                final String username = options.user ? userEntry.getText() : bookmark.getCredentials().getUsername();
                final String password = options.password && !options.oauth ? emptyToNull(passwordEntry.getText()) : null;
                final Credentials credentials = new Credentials(username, password);
                final String token = emptyToNull(tokenEntry.getText());
                if(token != null) {
                    // S3 keeps these tokens only when they are set on the bookmark. setToken() drops the access key.
                    final TemporaryAccessTokens tokens = new TemporaryAccessTokens(username, password, token);
                    credentials.setTokens(tokens);
                    bookmark.getCredentials().setTokens(new TemporaryAccessTokens(tokens));
                }
                if(options.publickey && keyEntry.getText() != null && !keyEntry.getText().isBlank()) {
                    credentials.setIdentity(new Local(keyEntry.getText().trim()));
                }
                result.set(credentials);
                dialog.close();
            });
            content.append(connect);
            dialog.setChild(content);
            dialog.onCloseRequest(() -> {
                latch.countDown();
                return false;
            });
            dialog.present();
        });
        await(latch);
        final Credentials credentials = result.get();
        if(credentials == null) {
            throw new LoginCanceledException();
        }
        return credentials;
    }

    @Override
    public Local select(final Local identity) throws LoginCanceledException {
        final AtomicReference<String> path = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        GLib.idleAddOnce(() -> {
            final Window dialog = new Window();
            dialog.setTitle("Select file");
            dialog.setModal(true);
            if(parent != null) {
                dialog.setTransientFor(parent);
            }
            final Box content = new Box(Orientation.VERTICAL, 8);
            content.setMarginStart(16);
            content.setMarginEnd(16);
            content.setMarginTop(16);
            content.setMarginBottom(16);
            final Entry entry = new Entry();
            if(identity != null) {
                entry.setText(identity.getAbsolute());
            }
            content.append(row("File", entry));
            final Button choose = Button.withLabel("Select");
            choose.onClicked(() -> {
                path.set(entry.getText());
                dialog.close();
            });
            content.append(choose);
            dialog.setChild(content);
            dialog.onCloseRequest(() -> {
                latch.countDown();
                return false;
            });
            dialog.present();
        });
        await(latch);
        if(path.get() == null || path.get().isBlank()) {
            throw new LoginCanceledException();
        }
        return new Local(path.get().trim());
    }

    @Override
    public void warn(final Host bookmark, final String title, final String message, final String defaultButton,
                     final String cancelButton, final String preference) throws ConnectionCanceledException {
        GtkQuestions.require(GtkQuestions.ask(parent, title, message,
                defaultButton == null ? "Continue" : defaultButton, cancelButton == null ? "Cancel" : cancelButton));
    }

    @Override
    public void await(final CountDownLatch signal, final Host bookmark, final String title, final String message) throws ConnectionCanceledException {
        try {
            signal.await();
        }
        catch(final InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ConnectionCanceledException(e);
        }
    }

    @Override
    public boolean verify(final Host hostname, final PublicKey key) throws BackgroundException {
        final String fingerprint = key == null ? "" : Base64.getEncoder().encodeToString(key.getEncoded());
        final String message = "The host key for " + hostname.getHostname()
                + (key == null ? " is unknown." : " (" + key.getAlgorithm() + ") is\n" + fingerprint);
        return GtkQuestions.ask(parent, "Unknown host key", message, "Allow", "Deny");
    }

    private static void await(final CountDownLatch latch) throws LoginCanceledException {
        try {
            latch.await();
        }
        catch(final InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LoginCanceledException(e);
        }
    }

    private static String emptyToNull(final String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static Widget row(final String labelText, final Widget field) {
        final Box box = new Box(Orientation.VERTICAL, 4);
        final Label label = new Label(labelText);
        label.setXalign(0);
        box.append(label);
        box.append(field);
        return box;
    }

}
