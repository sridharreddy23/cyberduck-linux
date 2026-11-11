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

import ch.cyberduck.core.UnsecureHostPasswordStore;
import ch.cyberduck.core.editor.DefaultEditorFactory;
import ch.cyberduck.core.transfer.Transfer;
import ch.cyberduck.core.i18n.RegexLocale;
import ch.cyberduck.core.local.DefaultSymlinkFeature;
import ch.cyberduck.core.local.ExecApplicationLauncher;
import ch.cyberduck.core.preferences.MemoryPreferences;
import ch.cyberduck.core.preferences.UserHomeSupportDirectoryFinder;
import ch.cyberduck.core.proxy.EnvironmentVariableProxyFinder;

/**
 * Preferences for the Linux browser, following the same factory wiring already proven by the
 * official Linux `duck` CLI build ({@code cli/linux}) for bookmark storage, password handling and
 * local filesystem access.
 */
public class LinuxPreferences extends MemoryPreferences {

    @Override
    protected void setDefaults() {
        super.setDefaults();
        this.setDefault("local.user.home", System.getProperty("user.home"));
        this.setDefault("connection.login.name", System.getProperty("user.name"));
        this.setDefault("logging", "fatal");
        // LinuxResourcesFinder unpacks *.cyberduckprofile into <root>/profiles.
        this.setDefault("profiles.folder.name", "profiles");
    }

    @Override
    protected void setFactories() {
        super.setFactories();
        this.setDefault("factory.applicationresourcesfinder.class", LinuxResourcesFinder.class.getName());
        this.setDefault("factory.supportdirectoryfinder.class", UserHomeSupportDirectoryFinder.class.getName());
        this.setDefault("factory.localsupportdirectoryfinder.class", UserHomeSupportDirectoryFinder.class.getName());
        this.setDefault("factory.locale.class", RegexLocale.class.getName());
        this.setDefault("factory.applicationlauncher.class", ExecApplicationLauncher.class.getName());
        this.setDefault("factory.editorfactory.class", DefaultEditorFactory.class.getName());
        this.setDefault("factory.proxy.class", EnvironmentVariableProxyFinder.class.getName());
        this.setDefault("factory.symlink.class", DefaultSymlinkFeature.class.getName());
        this.setDefault("factory.passwordstore.class", UnsecureHostPasswordStore.class.getName());
        this.setDefault("factory.browserlauncher.class", XdgBrowserLauncher.class.getName());
        // Same callback slots the Windows ApplicationPreferences installs for its dialogs.
        this.setDefault("factory.logincallback.class", GtkPrompts.class.getName());
        this.setDefault("factory.hostkeycallback.class", GtkPrompts.class.getName());
        this.setDefault("factory.passwordcallback.class", GtkPrompts.class.getName());
        this.setDefault("factory.certificatetrustcallback.class", GtkCertificateTrustCallback.class.getName());
        this.setDefault("factory.alertcallback.class", GtkAlertCallback.class.getName());
        for(Transfer.Type type : Transfer.Type.values()) {
            this.setDefault(String.format("factory.transferpromptcallback.%s.class", type.name()), GtkTransferPrompt.class.getName());
        }
    }
}
