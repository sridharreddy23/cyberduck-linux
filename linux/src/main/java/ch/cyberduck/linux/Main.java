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

import ch.cyberduck.core.Protocol;
import ch.cyberduck.core.ProtocolFactory;
import ch.cyberduck.core.preferences.PreferencesFactory;
import ch.cyberduck.core.serviceloader.AutoServiceLoaderFactory;

import org.gnome.adw.Application;
import org.gnome.adw.ColorScheme;
import org.gnome.adw.StyleManager;
import org.gnome.gdk.Display;
import org.gnome.gio.ApplicationFlags;
import org.gnome.gtk.CssProvider;
import org.gnome.gtk.Gtk;
import org.gnome.gtk.StyleContext;

public final class Main {

    /**
     * Windows Cyberduck ({@code BrowserForm.Designer.cs}) is a light-themed WinForms app with a
     * Segoe UI 11.25pt font, flat/square ToolStrip buttons and a plain white/light-gray palette.
     * This forces the same look regardless of the host's GNOME dark-mode/Adwaita theme: light
     * color scheme, square corners (GTK4 client-side-decoration windows are rounded by default),
     * Segoe UI's open substitute Selawik, and a Windows Forms-style gray toolbar / white content
     * / blue selection palette instead of Adwaita's.
     */
    private static void installStylesheet() {
        StyleManager.getDefault().setColorScheme(ColorScheme.FORCE_LIGHT);

        final CssProvider provider = new CssProvider();
        provider.loadFromString("""
                * {
                    font-family: "Selawik", "Noto Sans", sans-serif;
                    font-size: 10.5pt;
                }
                window, window.csd, window.csd decoration {
                    border-radius: 0;
                    box-shadow: none;
                    background-color: #F0F0F0;
                    color: #000000;
                }
                .win-titlebar {
                    background-color: #FFFFFF;
                    min-height: 30px;
                }
                .win-title {
                    font-weight: bold;
                    color: #000000;
                }
                .win-caption-btn, .win-caption-close {
                    border-radius: 0;
                    min-width: 46px;
                    min-height: 30px;
                    padding: 0;
                }
                .win-caption-btn:hover {
                    background-color: #E5E5E5;
                }
                .win-caption-close:hover {
                    background-color: #E81123;
                    color: #FFFFFF;
                }
                .win-toolbar {
                    background-color: #F0F0F0;
                    padding: 2px;
                }
                .win-toolbar button {
                    border-radius: 0;
                    background: none;
                    padding: 4px 8px;
                }
                .win-toolbar button:hover {
                    background-color: #E5F1FB;
                    border: 1px solid #CCE4F7;
                }
                .cyberduck-toolbar-button {
                    font-size: 9pt;
                }
                list, listview, scrolledwindow, .view {
                    background-color: #FFFFFF;
                    color: #000000;
                }
                row:selected {
                    background-color: #CCE8FF;
                    color: #000000;
                }
                """);
        StyleContext.addProviderForDisplay(Display.getDefault(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
    }

    private static void activate(final Application application) {
        installStylesheet();
        new BrowserWindow(application).present();
    }

    public static void main(final String[] args) {
        // Before any Cyberduck class loads AWT. AWT on Linux dlopens GTK 3.
        System.setProperty("java.awt.headless", "true");
        PreferencesFactory.set(new LinuxPreferences());
        final ProtocolFactory protocols = ProtocolFactory.get();
        for(final Protocol protocol : AutoServiceLoaderFactory.<Protocol>get().load(Protocol.class)) {
            protocols.register(protocol);
        }
        protocols.load();
        final Application application = new Application("ch.cyberduck.linux", ApplicationFlags.DEFAULT_FLAGS);
        application.onActivate(() -> activate(application));
        System.exit(application.run(args));
    }
}
