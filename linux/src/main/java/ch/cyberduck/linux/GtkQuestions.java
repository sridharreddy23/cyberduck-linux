/*
 * Copyright (c) 2002-2026 iterate GmbH. All rights reserved.
 * https://cyberduck.io/
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
package ch.cyberduck.linux;

import ch.cyberduck.core.exception.ConnectionCanceledException;

import org.gnome.glib.GLib;
import org.gnome.gtk.Box;
import org.gnome.gtk.Button;
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.Window;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Yes/no prompt marshalled onto the GTK thread. Callers are the background connection and transfer threads.
 */
final class GtkQuestions {

    private GtkQuestions() {
    }

    static boolean ask(final Window parent, final String title, final String message, final String yes, final String no) {
        final AtomicReference<Boolean> allowed = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        GLib.idleAddOnce(() -> {
            final Window dialog = new Window();
            dialog.setTitle(title == null ? "Cyberduck" : title);
            dialog.setModal(true);
            if(parent != null) {
                dialog.setTransientFor(parent);
            }
            dialog.setDefaultSize(460, 20);
            final Box content = new Box(Orientation.VERTICAL, 8);
            content.setMarginStart(16);
            content.setMarginEnd(16);
            content.setMarginTop(16);
            content.setMarginBottom(16);
            final Label label = new Label(message == null ? "" : message);
            label.setWrap(true);
            label.setXalign(0);
            content.append(label);
            final Box buttons = new Box(Orientation.HORIZONTAL, 8);
            final Button deny = Button.withLabel(no);
            deny.onClicked(() -> {
                allowed.set(false);
                dialog.close();
            });
            final Button allow = Button.withLabel(yes);
            allow.onClicked(() -> {
                allowed.set(true);
                dialog.close();
            });
            buttons.append(deny);
            buttons.append(allow);
            content.append(buttons);
            dialog.setChild(content);
            dialog.onCloseRequest(() -> {
                latch.countDown();
                return false;
            });
            dialog.present();
        });
        try {
            latch.await();
        }
        catch(final InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
        return Boolean.TRUE.equals(allowed.get());
    }

    static void require(final boolean accepted) throws ConnectionCanceledException {
        if(!accepted) {
            throw new ConnectionCanceledException();
        }
    }
}
