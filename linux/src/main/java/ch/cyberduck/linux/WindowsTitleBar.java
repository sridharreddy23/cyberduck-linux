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
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.Widget;
import org.gnome.gtk.Window;
import org.gnome.gtk.WindowHandle;

/**
 * Square, flat title bar with Windows-style caption buttons ("-", a restore/maximize glyph, "x"),
 * replacing GNOME/Adwaita's default rounded HeaderBar window controls. Wrapped in a
 * {@code Gtk.WindowHandle} so the blank area still drags/double-click-maximizes the window the
 * same way a native titlebar would.
 */
public final class WindowsTitleBar {

    private WindowsTitleBar() {
    }

    public static Widget build(final Window window, final String title) {
        final Box bar = new Box(Orientation.HORIZONTAL, 0);
        bar.addCssClass("win-titlebar");
        bar.setMarginStart(8);

        final Label titleLabel = new Label(title);
        titleLabel.addCssClass("win-title");
        bar.append(titleLabel);

        final Box spacer = new Box(Orientation.HORIZONTAL, 0);
        spacer.setHexpand(true);
        bar.append(spacer);

        final Button minimize = captionButton("–", "win-caption-btn");
        minimize.onClicked(window::minimize);
        bar.append(minimize);

        final Button maximize = captionButton("□", "win-caption-btn");
        maximize.onClicked(() -> {
            if(window.isMaximized()) {
                window.unmaximize();
            }
            else {
                window.maximize();
            }
        });
        bar.append(maximize);

        final Button close = captionButton("×", "win-caption-close");
        close.onClicked(window::close);
        bar.append(close);

        final WindowHandle handle = new WindowHandle();
        handle.setChild(bar);
        return handle;
    }

    private static Button captionButton(final String glyph, final String cssClass) {
        final Button button = new Button();
        button.setHasFrame(false);
        button.addCssClass(cssClass);
        final Label label = new Label(glyph);
        button.setChild(label);
        return button;
    }
}
