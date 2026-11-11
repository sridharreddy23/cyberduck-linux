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

import ch.cyberduck.core.AbstractController;
import ch.cyberduck.core.threading.MainAction;

import org.gnome.glib.GLib;
import org.gnome.glib.MainContext;
import org.gnome.gtk.Window;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

/**
 * GTK main-thread controller. {@link ch.cyberduck.core.SessionPoolFactory} and the transfer workers
 * take a {@link ch.cyberduck.core.Controller}, the same type the macOS and Windows browsers pass.
 */
public final class LinuxController extends AbstractController {

    private final Window window;
    private final Consumer<String> status;

    public LinuxController(final Window window, final Consumer<String> status) {
        this.window = window;
        this.status = status;
    }

    public Window window() {
        return window;
    }

    @Override
    public void invoke(final MainAction runnable, final boolean wait) {
        if(MainContext.default_().isOwner()) {
            runnable.run();
            return;
        }
        if(!wait) {
            GLib.idleAddOnce(runnable::run);
            return;
        }
        final CountDownLatch latch = new CountDownLatch(1);
        final AtomicReference<RuntimeException> failure = new AtomicReference<>();
        GLib.idleAddOnce(() -> {
            try {
                runnable.run();
            }
            catch(final RuntimeException e) {
                failure.set(e);
            }
            finally {
                latch.countDown();
            }
        });
        try {
            latch.await();
        }
        catch(final InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        if(failure.get() != null) {
            throw failure.get();
        }
    }

    @Override
    public void message(final String message) {
        super.message(message);
        if(message == null || message.isEmpty()) {
            return;
        }
        GLib.idleAddOnce(() -> status.accept(message));
    }
}
