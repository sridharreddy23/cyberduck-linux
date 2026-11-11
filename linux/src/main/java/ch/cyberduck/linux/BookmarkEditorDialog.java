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

import ch.cyberduck.core.BookmarkCollection;
import ch.cyberduck.core.Credentials;
import ch.cyberduck.core.Host;
import ch.cyberduck.core.Local;
import ch.cyberduck.core.Protocol;
import ch.cyberduck.core.TemporaryAccessTokens;

import org.gnome.gtk.Box;
import org.gnome.gtk.Button;
import org.gnome.gtk.DropDown;
import org.gnome.gtk.Entry;
import org.gnome.gtk.Label;
import org.gnome.gtk.Orientation;
import org.gnome.gtk.PasswordEntry;
import org.gnome.gtk.Widget;
import org.gnome.gtk.Window;

/**
 * New Bookmark dialog: same connection fields as Quick Connect, plus a nickname, persisted to
 * {@link BookmarkCollection#defaultCollection()} on save.
 */
public final class BookmarkEditorDialog {

    private BookmarkEditorDialog() {
    }

    public static void show(final Window parent, final QuickConnectDialog.ConnectHandler handler) {
        final Window dialog = new Window();
        dialog.setTitle("New Bookmark");
        dialog.setModal(true);
        dialog.setTransientFor(parent);
        dialog.setDefaultSize(380, 20);

        final Box content = new Box(Orientation.VERTICAL, 10);
        content.setMarginStart(16);
        content.setMarginEnd(16);
        content.setMarginTop(16);
        content.setMarginBottom(16);

        final Entry nicknameEntry = new Entry();
        nicknameEntry.setPlaceholderText("Bookmark name");
        final String[] labels = ProtocolChoice.labels();
        final DropDown protocolDropdown = DropDown.fromStrings(labels.length == 0 ? new String[]{"No protocols registered"} : labels);
        protocolDropdown.setSelected(ProtocolChoice.defaultIndex());
        final Entry hostEntry = new Entry();
        hostEntry.setPlaceholderText("Server. Leave empty when the protocol has a fixed host.");
        final Entry portEntry = new Entry();
        portEntry.setPlaceholderText("Default for protocol");
        final Entry pathEntry = new Entry();
        pathEntry.setPlaceholderText("Remote path (optional)");
        final Entry userEntry = new Entry();
        userEntry.setPlaceholderText("Username, access key, or account");
        final PasswordEntry passwordEntry = new PasswordEntry();
        passwordEntry.setShowPeekIcon(true);
        final PasswordEntry tokenEntry = new PasswordEntry();
        tokenEntry.setShowPeekIcon(true);
        final Entry identityEntry = new Entry();
        identityEntry.setPlaceholderText("Private key path (optional)");

        content.append(row("Nickname", nicknameEntry));
        content.append(row("Protocol", protocolDropdown));
        content.append(row("Server", hostEntry));
        content.append(row("Port", portEntry));
        content.append(row("Path", pathEntry));
        content.append(row("Username", userEntry));
        content.append(row("Password", passwordEntry));
        content.append(row("Session Token", tokenEntry));
        content.append(row("Private Key", identityEntry));

        final Label error = new Label("");
        error.setWrap(true);

        final Button save = Button.withLabel("Save & Connect");
        save.onClicked(() -> {
            if(ProtocolChoice.labels().length == 0) {
                error.setLabel("No protocols are registered.");
                return;
            }
            final Protocol protocol = ProtocolChoice.get(protocolDropdown.getSelected());
            String hostname = hostEntry.getText();
            if(hostname == null || hostname.isBlank()) {
                if(protocol.isHostnameConfigurable()) {
                    error.setLabel("Server is required.");
                    return;
                }
                hostname = protocol.getDefaultHostname();
                if(hostname == null || hostname.isBlank()) {
                    hostname = protocol.getIdentifier();
                }
            }
            int port = protocol.getDefaultPort();
            final String portText = portEntry.getText();
            if(portText != null && !portText.isBlank()) {
                try {
                    port = Integer.parseInt(portText.trim());
                }
                catch(NumberFormatException ignored) {
                    // keep protocol default
                }
            }
            final String user = userEntry.getText();
            final String password = passwordEntry.getText();
            final String token = tokenEntry.getText();
            final String identity = identityEntry.getText();
            final Credentials credentials = new Credentials(user, password == null || password.isEmpty() ? null : password);
            if(token != null && !token.isBlank()) {
                credentials.setTokens(new TemporaryAccessTokens(user, credentials.getPassword(), token.trim()));
            }
            if(identity != null && !identity.isBlank()) {
                credentials.setIdentity(new Local(identity.trim()));
            }
            final Host host = new Host(protocol, hostname.trim(), port, credentials);
            final String path = pathEntry.getText();
            if(path != null && !path.isBlank()) {
                host.setDefaultPath(path.trim());
            }
            final String nickname = nicknameEntry.getText();
            if(nickname != null && !nickname.isBlank()) {
                host.setNickname(nickname.trim());
            }
            BookmarkCollection.defaultCollection().add(host);
            dialog.close();
            handler.onConnect(host);
        });
        content.append(save);
        content.append(error);

        dialog.setChild(content);
        dialog.present();
    }

    private static Widget row(final String labelText, final Widget field) {
        final Box box = new Box(Orientation.VERTICAL, 4);
        final Label label = new Label(labelText);
        label.setXalign(0);
        box.append(label);
        box.append(field);
        return box;
    }
}
