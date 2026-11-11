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

import ch.cyberduck.core.Host;
import ch.cyberduck.core.SessionPoolFactory;
import ch.cyberduck.core.exception.BackgroundException;
import ch.cyberduck.core.pool.SessionPool;
import ch.cyberduck.core.threading.TransferBackgroundAction;
import ch.cyberduck.core.transfer.Transfer;
import ch.cyberduck.core.transfer.TransferAdapter;
import ch.cyberduck.core.transfer.TransferOptions;
import ch.cyberduck.core.transfer.TransferProgress;
import ch.cyberduck.core.transfer.TransferQueueFactory;

import org.gnome.glib.GLib;

/**
 * Starts a transfer the way the Windows browser does. The default {@code queue.transfer.type} is
 * {@code concurrent}, which opens a transfer pool and runs {@link ch.cyberduck.core.worker.ConcurrentTransferWorker}.
 * {@link Host.TransferType#browser} reuses the browser pool instead.
 */
final class LinuxTransfers {

    private LinuxTransfers() {
    }

    static void start(final LinuxController controller, final SessionPool browser, final Transfer transfer, final Runnable onComplete) {
        final TransferQueueWindow.Handle handle = TransferQueueWindow.get().addTransfer(transfer.getName());
        final boolean useBrowser = Host.TransferType.getType(transfer.getSource()).equals(Host.TransferType.browser);
        final SessionPool source = useBrowser
                ? browser
                : SessionPoolFactory.create(controller, transfer.getSource(), controller);
        final SessionPool destination = transfer.getType() == Transfer.Type.copy
                ? SessionPoolFactory.create(controller, transfer.getDestination(), controller)
                : SessionPool.DISCONNECTED;
        controller.background(new TransferBackgroundAction(controller, source, destination, TransferQueueFactory.get(),
                new TransferAdapter() {
                    @Override
                    public void transferDidProgress(final Transfer t, final TransferProgress status) {
                        final long size = status.getSize() == null ? 0L : status.getSize();
                        final long transferred = status.getTransferred() == null ? 0L : status.getTransferred();
                        final double fraction = size > 0 ? (double) transferred / size : 0;
                        final String text = status.getProgress() == null || status.getProgress().isEmpty()
                                ? transferred + " / " + size : status.getProgress();
                        GLib.idleAddOnce(() -> handle.progress(fraction, text));
                    }

                    @Override
                    public void transferDidStop(final Transfer t) {
                        GLib.idleAddOnce(() -> {
                            if(t.isComplete()) {
                                handle.complete("Completed.");
                                onComplete.run();
                            }
                        });
                    }
                }, controller, transfer, new TransferOptions()) {
            @Override
            public void cleanup(final Boolean result, final BackgroundException failure) {
                super.cleanup(result, failure);
                if(failure != null) {
                    final String message = failure.getMessage() == null ? "Transfer failed." : failure.getMessage();
                    handle.failed(message);
                }
            }
        });
    }
}
