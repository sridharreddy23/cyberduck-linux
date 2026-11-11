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

import org.gnome.gtk.Box;
import org.gnome.gtk.Label;
import org.gnome.gtk.ListBox;
import org.gnome.gtk.ListBoxRow;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.ProgressBar;
import org.gnome.gtk.ScrolledWindow;
import org.gnome.gtk.Window;

/**
 * Transfer queue window: one row per transfer with a progress bar, mirroring the Mac/Windows
 * transfer window. Created lazily on the first transfer.
 */
public final class TransferQueueWindow {

    private static TransferQueueWindow instance;

    private final Window window = new Window();
    private final ListBox list = new ListBox();

    private TransferQueueWindow() {
        window.setTitle("Transfers");
        window.setDefaultSize(480, 260);
        final ScrolledWindow scrolled = new ScrolledWindow();
        scrolled.setVexpand(true);
        scrolled.setChild(list);
        window.setChild(scrolled);
    }

    public static TransferQueueWindow get() {
        if(instance == null) {
            instance = new TransferQueueWindow();
        }
        return instance;
    }

    public void show() {
        window.present();
    }

    public Handle addTransfer(final String name) {
        final ListBoxRow row = new ListBoxRow();
        final Box box = new Box(Orientation.VERTICAL, 4);
        box.setMarginStart(8);
        box.setMarginEnd(8);
        box.setMarginTop(6);
        box.setMarginBottom(6);
        final Label nameLabel = new Label(name);
        nameLabel.setXalign(0);
        box.append(nameLabel);
        final ProgressBar progressBar = new ProgressBar();
        box.append(progressBar);
        final Label statusLabel = new Label("Starting…");
        statusLabel.setXalign(0);
        statusLabel.addCssClass("dim-label");
        box.append(statusLabel);
        row.setChild(box);
        list.append(row);
        this.show();
        return new Handle(progressBar, statusLabel);
    }

    public static final class Handle {
        private final ProgressBar progressBar;
        private final Label statusLabel;

        private Handle(final ProgressBar progressBar, final Label statusLabel) {
            this.progressBar = progressBar;
            this.statusLabel = statusLabel;
        }

        public void progress(final double fraction, final String status) {
            progressBar.setFraction(Math.min(1.0, Math.max(0.0, fraction)));
            statusLabel.setLabel(status);
        }

        public void complete(final String status) {
            progressBar.setFraction(1.0);
            statusLabel.setLabel(status);
        }

        public void failed(final String status) {
            statusLabel.setLabel(status);
        }
    }
}
