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
import ch.cyberduck.core.Host;
import ch.cyberduck.core.exception.BackgroundException;
import ch.cyberduck.core.threading.AlertCallback;

import org.gnome.gtk.Window;

/**
 * Failure prompt for background workers. Returning true asks the transfer and session actions to retry,
 * which is what the macOS and Windows alert callbacks do.
 */
public final class GtkAlertCallback implements AlertCallback {

    private final Window parent;

    public GtkAlertCallback(final Controller controller) {
        this.parent = controller instanceof LinuxController ? ((LinuxController) controller).window() : null;
    }

    @Override
    public boolean alert(final Host host, final BackgroundException failure) {
        final String detail = failure.getDetail();
        final String message = detail == null || detail.isBlank() ? failure.getMessage() : detail;
        return GtkQuestions.ask(parent, failure.getMessage() == null ? "Error" : failure.getMessage(),
                message == null ? "The operation failed." : message, "Try Again", "Cancel");
    }
}
