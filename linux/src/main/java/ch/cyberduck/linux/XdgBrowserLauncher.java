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

import ch.cyberduck.core.local.BrowserLauncher;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

/**
 * Opens URLs with {@code xdg-open}. {@code java.awt.Desktop} loads GTK 3, and this process
 * already uses GTK 4. Loading both registers {@code GdkDisplayManager} twice and the window dies.
 */
public final class XdgBrowserLauncher implements BrowserLauncher {
    private static final Logger log = LogManager.getLogger(XdgBrowserLauncher.class);

    @Override
    public boolean open(final String url) {
        try {
            new ProcessBuilder("xdg-open", url).start();
            return true;
        }
        catch(final IOException e) {
            log.warn("Failure opening {} with xdg-open", url, e);
            return false;
        }
    }
}
