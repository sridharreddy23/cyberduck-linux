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
import org.gnome.gtk.Button;
import org.gnome.gtk.Entry;
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.Window;

/**
 * Prompts for a single local filesystem path via a plain text entry.
 * <p>
 * Deliberately avoids {@code Gtk.FileDialog}: its async portal-backed implementation crashed the
 * whole JVM in this environment (a java-gi/FFM memory arena gets closed while still "acquired" on
 * {@code Application.run()} return, right after GTK logs "GtkListBoxRow has no property named
 * 'label'/'section-type'" from the native chooser's internal sidebar - consistent with a
 * misbehaving or unavailable xdg-desktop-portal file chooser backend). A plain entry has none of
 * that risk.
 */
public final class PathEntryDialog {

    private PathEntryDialog() {
    }

    public interface PathHandler {
        void onPath(String path);
    }

    public static void show(final Window parent, final String title, final String fieldLabel,
                             final String initialValue, final String actionLabel, final PathHandler handler) {
        final Window dialog = new Window();
        dialog.setTitle(title);
        dialog.setModal(true);
        dialog.setTransientFor(parent);
        dialog.setDefaultSize(420, 20);

        final Box content = new Box(Orientation.VERTICAL, 10);
        content.setMarginStart(16);
        content.setMarginEnd(16);
        content.setMarginTop(16);
        content.setMarginBottom(16);

        final Label label = new Label(fieldLabel);
        label.setXalign(0);
        content.append(label);

        final Entry entry = new Entry();
        entry.setText(initialValue);
        content.append(entry);

        final Label error = new Label("");
        error.setWrap(true);

        final Button action = Button.withLabel(actionLabel);
        action.onClicked(() -> {
            final String path = entry.getText();
            if(path == null || path.isBlank()) {
                error.setLabel("Path is required.");
                return;
            }
            dialog.close();
            handler.onPath(path.trim());
        });
        content.append(action);
        content.append(error);

        dialog.setChild(content);
        dialog.present();
    }
}
