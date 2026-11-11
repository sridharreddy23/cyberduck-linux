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

import ch.cyberduck.core.Controller;
import ch.cyberduck.core.pool.SessionPool;
import ch.cyberduck.core.transfer.Transfer;
import ch.cyberduck.core.transfer.TransferAction;
import ch.cyberduck.core.transfer.TransferItem;
import ch.cyberduck.core.transfer.TransferPrompt;

import org.gnome.glib.GLib;
import org.gnome.gtk.Box;
import org.gnome.gtk.Button;
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.Window;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Existing-file prompt. The default action is {@code ask}; without a prompt the core cancels the transfer.
 */
public final class GtkTransferPrompt implements TransferPrompt {

    private final Window parent;

    public GtkTransferPrompt(final Controller controller, final Transfer transfer, final SessionPool source, final SessionPool destination) {
        this.parent = controller instanceof LinuxController ? ((LinuxController) controller).window() : null;
    }

    @Override
    public TransferAction prompt(final TransferItem file) {
        final String name = file.local != null ? file.local.getName() : file.remote.getName();
        final AtomicReference<TransferAction> choice = new AtomicReference<>(TransferAction.cancel);
        final CountDownLatch latch = new CountDownLatch(1);
        GLib.idleAddOnce(() -> {
            final Window dialog = new Window();
            dialog.setTitle("File exists");
            dialog.setModal(true);
            if(parent != null) {
                dialog.setTransientFor(parent);
            }
            dialog.setDefaultSize(420, 20);
            final Box content = new Box(Orientation.VERTICAL, 8);
            content.setMarginStart(16);
            content.setMarginEnd(16);
            content.setMarginTop(16);
            content.setMarginBottom(16);
            final Label label = new Label(name + " already exists. Choose how to continue.");
            label.setWrap(true);
            label.setXalign(0);
            content.append(label);
            final Box buttons = new Box(Orientation.HORIZONTAL, 8);
            buttons.append(choiceButton(dialog, choice, latch, "Cancel", TransferAction.cancel));
            buttons.append(choiceButton(dialog, choice, latch, "Resume", TransferAction.resume));
            buttons.append(choiceButton(dialog, choice, latch, "Overwrite", TransferAction.overwrite));
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
            return TransferAction.cancel;
        }
        return choice.get();
    }

    private static Button choiceButton(final Window dialog, final AtomicReference<TransferAction> choice, final CountDownLatch latch,
                                        final String label, final TransferAction action) {
        final Button button = Button.withLabel(label);
        button.onClicked(() -> {
            choice.set(action);
            dialog.close();
        });
        return button;
    }

    @Override
    public boolean isSelected(final TransferItem file) {
        return true;
    }

    @Override
    public void message(final String message) {
        // Status text is already shown by the controller.
    }
}
