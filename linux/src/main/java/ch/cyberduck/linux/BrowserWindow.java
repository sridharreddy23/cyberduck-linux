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

import ch.cyberduck.core.AttributedList;
import ch.cyberduck.core.BookmarkCollection;
import ch.cyberduck.core.CollectionListener;
import ch.cyberduck.core.DisabledListProgressListener;
import ch.cyberduck.core.Host;
import ch.cyberduck.core.LocalFactory;
import ch.cyberduck.core.LoginCallbackFactory;
import ch.cyberduck.core.Path;
import ch.cyberduck.core.PathCache;
import ch.cyberduck.core.SessionPoolFactory;
import ch.cyberduck.core.exception.BackgroundException;
import ch.cyberduck.core.pool.SessionPool;
import ch.cyberduck.core.preferences.PreferencesFactory;
import ch.cyberduck.core.threading.WorkerBackgroundAction;
import ch.cyberduck.core.transfer.DownloadTransfer;
import ch.cyberduck.core.transfer.UploadTransfer;
import ch.cyberduck.core.worker.CreateDirectoryWorker;
import ch.cyberduck.core.worker.DeleteWorker;
import ch.cyberduck.core.worker.ListWorker;
import ch.cyberduck.core.worker.MountWorker;

import org.gnome.gtk.Application;
import org.gnome.gtk.ApplicationWindow;
import org.gnome.gtk.Box;
import org.gnome.gtk.Button;
import org.gnome.gtk.Image;
import org.gnome.gtk.Label;
import org.gnome.gtk.ListBox;
import org.gnome.gtk.ListBoxRow;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.Paned;
import org.gnome.gtk.ScrolledWindow;
import org.gnome.gtk.SelectionMode;
import org.gnome.gtk.Separator;
import org.gnome.gtk.Window;

import java.io.File;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;

/**
 * Main browser window: toolbar, file list and status bar, mirroring the layout shared by the
 * existing Mac/Windows Cyberduck browsers. Connect, list, and transfer go through the same
 * {@link SessionPoolFactory}, {@link MountWorker}, {@link ListWorker}, and
 * {@link ch.cyberduck.core.threading.TransferBackgroundAction} path as the Windows browser.
 */
public final class BrowserWindow {

    private static final DateTimeFormatter MODIFIED_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
            .withZone(ZoneId.systemDefault());

    private final ApplicationWindow window;
    private final ListBox fileList = new ListBox();
    private final ListBox bookmarkList = new ListBox();
    private final Label pathLabel = new Label("Not connected");
    private final Label statusLabel = new Label("Not connected.");
    private final Button refreshButton = toolbarButton("view-refresh-symbolic", "Refresh");
    private final Button downloadButton = toolbarButton("document-save-symbolic", "Download");
    private final Button uploadButton = toolbarButton("document-send-symbolic", "Upload");
    private final Button transfersButton = toolbarButton("list-compact-symbolic", "Transfers");
    private final Button disconnectButton = toolbarButton("process-stop-symbolic", "Disconnect");

    private final List<Path> currentListing = new ArrayList<>();
    private final List<Host> currentBookmarks = new ArrayList<>();
    private final LinuxController controller;
    private SessionPool pool = SessionPool.DISCONNECTED;
    private PathCache cache = new PathCache(PreferencesFactory.get().getInteger("browser.cache.size"));
    private Path workdir;

    public BrowserWindow(final Application application) {
        this.window = new ApplicationWindow(application);
        this.controller = new LinuxController(window, this::setStatus);
        window.setTitle("Cyberduck");
        window.setDefaultSize(820, 520);
        window.setTitlebar(WindowsTitleBar.build(window, "Cyberduck"));

        final Box toolbar = new Box(Orientation.HORIZONTAL, 0);
        toolbar.addCssClass("win-toolbar");
        // Button order follows the Windows toolbar (windows/.../BrowserForm.Designer.cs).
        final Button quickConnect = toolbarButton("list-add-symbolic", "Open Connection");
        quickConnect.onClicked(this::onQuickConnect);
        toolbar.append(quickConnect);

        refreshButton.setSensitive(false);
        refreshButton.onClicked(() -> {
            if(workdir != null) {
                cache.invalidate(workdir);
                list(workdir);
            }
        });
        toolbar.append(refreshButton);

        final Button newFolderButton = toolbarButton("folder-new-symbolic", "New Folder");
        newFolderButton.onClicked(this::onNewFolder);
        toolbar.append(newFolderButton);

        final Button deleteButton = toolbarButton("edit-delete-symbolic", "Delete");
        deleteButton.onClicked(this::onDelete);
        toolbar.append(deleteButton);

        downloadButton.setSensitive(false);
        downloadButton.onClicked(this::onDownload);
        toolbar.append(downloadButton);

        uploadButton.setSensitive(false);
        uploadButton.onClicked(this::onUpload);
        toolbar.append(uploadButton);

        transfersButton.onClicked(() -> TransferQueueWindow.get().show());
        toolbar.append(transfersButton);

        final Box toolbarSpacer = new Box(Orientation.HORIZONTAL, 0);
        toolbarSpacer.setHexpand(true);
        toolbar.append(toolbarSpacer);

        disconnectButton.setSensitive(false);
        disconnectButton.onClicked(this::disconnect);
        toolbar.append(disconnectButton);

        fileList.setSelectionMode(SelectionMode.SINGLE);
        fileList.onRowActivated(this::onRowActivated);

        final ScrolledWindow scrolled = new ScrolledWindow();
        scrolled.setVexpand(true);
        scrolled.setChild(fileList);

        pathLabel.setXalign(0);
        pathLabel.setMarginStart(8);
        pathLabel.setMarginTop(4);
        pathLabel.setMarginBottom(4);

        final Box browserContent = new Box(Orientation.VERTICAL, 0);
        browserContent.append(pathLabel);
        browserContent.append(new Separator(Orientation.HORIZONTAL));
        browserContent.append(scrolled);

        final Box sidebarHeader = new Box(Orientation.HORIZONTAL, 4);
        sidebarHeader.setMarginStart(8);
        sidebarHeader.setMarginEnd(4);
        sidebarHeader.setMarginTop(4);
        sidebarHeader.setMarginBottom(4);
        final Label sidebarTitle = new Label("Bookmarks");
        sidebarTitle.setXalign(0);
        sidebarTitle.setHexpand(true);
        sidebarHeader.append(sidebarTitle);
        final Button newBookmark = Button.fromIconName("list-add-symbolic");
        newBookmark.onClicked(() -> BookmarkEditorDialog.show(window, this::connect));
        sidebarHeader.append(newBookmark);

        bookmarkList.setSelectionMode(SelectionMode.SINGLE);
        bookmarkList.onRowActivated(this::onBookmarkActivated);
        final ScrolledWindow bookmarkScrolled = new ScrolledWindow();
        bookmarkScrolled.setVexpand(true);
        bookmarkScrolled.setChild(bookmarkList);

        final Box sidebar = new Box(Orientation.VERTICAL, 0);
        sidebar.append(sidebarHeader);
        sidebar.append(new Separator(Orientation.HORIZONTAL));
        sidebar.append(bookmarkScrolled);

        final Paned paned = new Paned(Orientation.HORIZONTAL);
        paned.setStartChild(sidebar);
        paned.setResizeStartChild(false);
        paned.setShrinkStartChild(false);
        paned.setEndChild(browserContent);
        paned.setPosition(200);
        paned.setVexpand(true);

        statusLabel.setXalign(0);
        statusLabel.setMarginStart(8);
        statusLabel.setMarginTop(4);
        statusLabel.setMarginBottom(4);

        final Box root = new Box(Orientation.VERTICAL, 0);
        root.append(toolbar);
        root.append(new Separator(Orientation.HORIZONTAL));
        root.append(paned);
        root.append(new Separator(Orientation.HORIZONTAL));
        root.append(statusLabel);

        window.setChild(root);

        final BookmarkCollection bookmarks = BookmarkCollection.defaultCollection();
        bookmarks.addListener(new CollectionListener<Host>() {
            @Override
            public void collectionLoaded() {
                renderBookmarks();
            }

            @Override
            public void collectionItemAdded(final Host item) {
                renderBookmarks();
            }

            @Override
            public void collectionItemRemoved(final Host item) {
                renderBookmarks();
            }

            @Override
            public void collectionItemChanged(final Host item) {
                renderBookmarks();
            }
        });
        try {
            bookmarks.load();
        }
        catch(final Exception e) {
            setStatus("Failed to load bookmarks: " + e.getMessage());
        }
    }

    public void present() {
        window.present();
    }

    private void onQuickConnect() {
        QuickConnectDialog.show(window, this::connect);
    }

    private void connect(final Host host) {
        final SessionPool previous = pool;
        pool = SessionPool.DISCONNECTED;
        workdir = null;
        if(previous != SessionPool.DISCONNECTED) {
            new Thread(previous::shutdown, "cyberduck-disconnect").start();
        }
        cache = new PathCache(PreferencesFactory.get().getInteger("browser.cache.size"));
        setStatus("Connecting to " + host.getHostname() + "…");
        final SessionPool next = SessionPoolFactory.create(controller, host, SessionPoolFactory.Usage.browser);
        pool = next;
        controller.background(new WorkerBackgroundAction<Path>(controller, next,
                new MountWorker(host, cache, new DisabledListProgressListener())) {
            @Override
            public void cleanup(final Path result, final BackgroundException failure) {
                super.cleanup(result, failure);
                if(BrowserWindow.this.pool != next) {
                    return;
                }
                if(failure != null || result == null) {
                    BrowserWindow.this.pool = SessionPool.DISCONNECTED;
                    final String message = failure == null ? "Connection failed." : failure.getMessage();
                    setStatus(message == null ? "Connection failed." : message);
                    new Thread(next::shutdown, "cyberduck-disconnect").start();
                    return;
                }
                disconnectButton.setSensitive(true);
                refreshButton.setSensitive(true);
                downloadButton.setSensitive(true);
                uploadButton.setSensitive(true);
                renderListing(result, cache.get(result));
            }
        });
    }

    private void disconnect() {
        final SessionPool closing = pool;
        pool = SessionPool.DISCONNECTED;
        workdir = null;
        cache.clear();
        currentListing.clear();
        fileList.removeAll();
        disconnectButton.setSensitive(false);
        refreshButton.setSensitive(false);
        downloadButton.setSensitive(false);
        uploadButton.setSensitive(false);
        pathLabel.setLabel("Not connected");
        setStatus("Not connected.");
        if(closing != SessionPool.DISCONNECTED) {
            new Thread(closing::shutdown, "cyberduck-disconnect").start();
        }
    }

    private void renderBookmarks() {
        currentBookmarks.clear();
        bookmarkList.removeAll();
        for(final Host bookmark : BookmarkCollection.defaultCollection()) {
            currentBookmarks.add(bookmark);
            bookmarkList.append(bookmarkRow(bookmark));
        }
    }

    private ListBoxRow bookmarkRow(final Host bookmark) {
        final ListBoxRow row = new ListBoxRow();
        final Box box = new Box(Orientation.VERTICAL, 2);
        box.setMarginStart(8);
        box.setMarginEnd(8);
        box.setMarginTop(4);
        box.setMarginBottom(4);
        final Label nickname = new Label(bookmark.getNickname());
        nickname.setXalign(0);
        box.append(nickname);
        final Label hostname = new Label(bookmark.getHostname());
        hostname.setXalign(0);
        hostname.addCssClass("dim-label");
        box.append(hostname);
        row.setChild(box);
        return row;
    }

    private void onBookmarkActivated(final ListBoxRow row) {
        final int index = row.getIndex();
        if(index < 0 || index >= currentBookmarks.size()) {
            return;
        }
        connect(currentBookmarks.get(index));
    }

    private void onDownload() {
        final ListBoxRow selectedRow = fileList.getSelectedRow();
        if(selectedRow == null) {
            return;
        }
        final int index = selectedRow.getIndex();
        if(index < 0 || index >= currentListing.size() || pool == SessionPool.DISCONNECTED || workdir == null) {
            return;
        }
        if(!workdir.isRoot() && index == 0) {
            return;
        }
        final Path remote = currentListing.get(index);
        final String suggested = System.getProperty("user.home") + "/Downloads/" + remote.getName();
        PathEntryDialog.show(window, "Download " + remote.getName(), "Save as", suggested, "Download", path -> {
            final DownloadTransfer transfer = new DownloadTransfer(pool.getHost(), remote, LocalFactory.get(path)).withCache(cache);
            LinuxTransfers.start(controller, pool, transfer, () -> {
                setStatus("Downloaded " + remote.getName() + ".");
                if(workdir != null) {
                    cache.invalidate(workdir);
                    list(workdir);
                }
            });
        });
    }

    private void onNewFolder() {
        if(pool == SessionPool.DISCONNECTED || workdir == null) {
            setStatus("Connect before creating a folder.");
            return;
        }
        PathEntryDialog.show(window, "New Folder", "Folder name", "New Folder", "Create", name -> {
            final String folderName = new File(name).getName();
            if(folderName == null || folderName.isBlank()) {
                setStatus("Folder name is required.");
                return;
            }
            final Path folder = new Path(workdir, folderName, EnumSet.of(Path.Type.directory));
            final Path parent = workdir;
            controller.background(new WorkerBackgroundAction<Path>(controller, pool, new CreateDirectoryWorker(folder, pool.getHost().getRegion())) {
                @Override
                public void cleanup(final Path result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    if(failure != null) {
                        setStatus("Create folder failed: " + failure.getMessage());
                        return;
                    }
                    setStatus("Created " + folderName + ".");
                    cache.invalidate(parent);
                    list(parent);
                }
            });
        });
    }

    private void onDelete() {
        final ListBoxRow selectedRow = fileList.getSelectedRow();
        if(selectedRow == null || pool == SessionPool.DISCONNECTED || workdir == null) {
            return;
        }
        final int index = selectedRow.getIndex();
        if(index < 0 || index >= currentListing.size()) {
            return;
        }
        final Path remote = currentListing.get(index);
        if(!workdir.isRoot() && index == 0) {
            return;
        }
        final Window dialog = new Window();
        dialog.setTitle("Delete");
        dialog.setModal(true);
        dialog.setTransientFor(window);
        final Box content = new Box(Orientation.VERTICAL, 8);
        content.setMarginStart(16);
        content.setMarginEnd(16);
        content.setMarginTop(16);
        content.setMarginBottom(16);
        final Label message = new Label("Delete " + remote.getName() + "?");
        message.setXalign(0);
        content.append(message);
        final Button confirm = Button.withLabel("Delete");
        confirm.onClicked(() -> {
            dialog.close();
            final Path parent = workdir;
            controller.background(new WorkerBackgroundAction<>(controller, pool,
                    new DeleteWorker(LoginCallbackFactory.get(controller), java.util.Collections.singletonList(remote), controller, cache)) {
                @Override
                public void cleanup(final java.util.List<Path> result, final BackgroundException failure) {
                    super.cleanup(result, failure);
                    if(failure != null) {
                        setStatus("Delete failed: " + failure.getMessage());
                        return;
                    }
                    setStatus("Deleted " + remote.getName() + ".");
                    cache.invalidate(parent);
                    list(parent);
                }
            });
        });
        content.append(confirm);
        dialog.setChild(content);
        dialog.present();
    }

    private void onUpload() {
        if(pool == SessionPool.DISCONNECTED || workdir == null) {
            return;
        }
        PathEntryDialog.show(window, "Upload to " + workdir.getAbsolute(), "Local file", System.getProperty("user.home") + "/", "Upload", path -> {
            final ch.cyberduck.core.Local local = LocalFactory.get(path);
            if(!local.exists()) {
                setStatus("Upload failed: " + path + " does not exist.");
                return;
            }
            final Path remote = new Path(workdir, local.getName(), local.isDirectory()
                    ? EnumSet.of(Path.Type.directory) : EnumSet.of(Path.Type.file));
            final UploadTransfer transfer = new UploadTransfer(pool.getHost(), remote, local);
            transfer.withCache(cache);
            final Path parent = workdir;
            LinuxTransfers.start(controller, pool, transfer, () -> {
                setStatus("Uploaded " + local.getName() + ".");
                cache.invalidate(parent);
                list(parent);
            });
        });
    }

    /**
     * Icon-above-label-below button, matching the toolbar style shared by Cyberduck's Windows
     * and Mac browsers (see {@code ImageAlign = ContentAlignment.BottomCenter} in
     * {@code BrowserForm.Designer.cs}), rather than GTK's usual side-by-side icon+label.
     */
    private static Button toolbarButton(final String icon, final String label) {
        final Button button = new Button();
        button.setHasFrame(false);
        final Box content = new Box(Orientation.VERTICAL, 2);
        content.append(Image.fromIconName(icon));
        final Label text = new Label(label);
        text.addCssClass("cyberduck-toolbar-button");
        content.append(text);
        button.setChild(content);
        return button;
    }

    private void onRowActivated(final ListBoxRow row) {
        final int index = row.getIndex();
        if(index < 0 || index >= currentListing.size()) {
            return;
        }
        final Path selected = currentListing.get(index);
        if(selected.isDirectory()) {
            list(selected);
        }
    }

    private void list(final Path directory) {
        if(pool == SessionPool.DISCONNECTED || directory == null) {
            return;
        }
        setStatus("Listing " + directory.getAbsolute() + "…");
        controller.background(new WorkerBackgroundAction<AttributedList<Path>>(controller, pool,
                new ListWorker(cache, directory, new DisabledListProgressListener())) {
            @Override
            public void cleanup(final AttributedList<Path> result, final BackgroundException failure) {
                super.cleanup(result, failure);
                if(failure != null) {
                    setStatus("Failed to list " + directory.getAbsolute() + ": " + failure.getMessage());
                    return;
                }
                renderListing(directory, result);
            }
        });
    }

    private void renderListing(final Path directory, final AttributedList<Path> entries) {
        workdir = directory;
        currentListing.clear();
        fileList.removeAll();
        pathLabel.setLabel(directory.getAbsolute());

        if(!directory.isRoot()) {
            currentListing.add(directory.getParent());
            fileList.append(fileRow("..", "", "", true));
        }
        int shown = 0;
        if(entries != null) {
            for(final Path entry : entries) {
                if(".".equals(entry.getName()) || "..".equals(entry.getName())) {
                    continue;
                }
                currentListing.add(entry);
                final long bytes = entry.attributes().getSize();
                final String size = entry.isDirectory() || bytes < 0 ? "" : humanReadableSize(bytes);
                final String modified = entry.attributes().getModificationDate() > 0
                        ? MODIFIED_FORMAT.format(Instant.ofEpochMilli(entry.attributes().getModificationDate())) : "";
                fileList.append(fileRow(entry.getName(), size, modified, entry.isDirectory()));
                shown++;
            }
        }
        setStatus(shown + " items.");
    }

    private ListBoxRow fileRow(final String name, final String size, final String modified, final boolean directory) {
        final ListBoxRow row = new ListBoxRow();
        final Box box = new Box(Orientation.HORIZONTAL, 12);
        box.setMarginStart(8);
        box.setMarginEnd(8);
        box.setMarginTop(4);
        box.setMarginBottom(4);

        final Label nameLabel = new Label(directory ? name + "/" : name);
        nameLabel.setXalign(0);
        nameLabel.setHexpand(true);
        box.append(nameLabel);

        final Label sizeLabel = new Label(size);
        sizeLabel.setWidthChars(10);
        sizeLabel.setXalign(1);
        box.append(sizeLabel);

        final Label modifiedLabel = new Label(modified);
        modifiedLabel.setWidthChars(16);
        modifiedLabel.setXalign(1);
        box.append(modifiedLabel);

        row.setChild(box);
        return row;
    }

    private void setStatus(final String text) {
        statusLabel.setLabel(text);
    }

    private static String humanReadableSize(final long bytes) {
        if(bytes < 1024) {
            return bytes + " B";
        }
        final int exponent = (int) (Math.log(bytes) / Math.log(1024));
        final String unit = "KMGTPE".charAt(exponent - 1) + "B";
        return String.format("%.1f %s", bytes / Math.pow(1024, exponent), unit);
    }
}
