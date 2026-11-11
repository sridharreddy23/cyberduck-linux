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

import ch.cyberduck.core.AttributedList;
import ch.cyberduck.core.Credentials;
import ch.cyberduck.core.DisabledListProgressListener;
import ch.cyberduck.core.DisabledLoginCallback;
import ch.cyberduck.core.DisabledPasswordStore;
import ch.cyberduck.core.Host;
import ch.cyberduck.core.HostKeyCallback;
import ch.cyberduck.core.ListService;
import ch.cyberduck.core.Local;
import ch.cyberduck.core.LoginConnectionService;
import ch.cyberduck.core.Path;
import ch.cyberduck.core.ProgressListener;
import ch.cyberduck.core.sftp.SFTPProtocol;
import ch.cyberduck.core.sftp.SFTPSession;
import ch.cyberduck.core.ssl.DefaultX509KeyManager;
import ch.cyberduck.core.ssl.DisabledX509TrustManager;
import ch.cyberduck.core.threading.CancelCallback;

import java.util.EnumSet;

/**
 * Phase 3 smoke test: connect over SFTP using the real core/ssh modules and list a directory,
 * with no UI involved yet.
 */
public final class SftpSmokeTest {

    public static void main(final String[] args) throws Exception {
        final String hostname = args[0];
        final int port = Integer.parseInt(args[1]);
        final String user = args[2];
        final String identity = args[3];
        final String remotePath = args[4];

        final Credentials credentials = new Credentials(user, null);
        credentials.setIdentity(new Local(identity));

        final Host host = new Host(new SFTPProtocol(), hostname, port, credentials);
        final SFTPSession session = new SFTPSession(host, new DisabledX509TrustManager(), new DefaultX509KeyManager());

        new LoginConnectionService(new DisabledLoginCallback(), HostKeyCallback.noop,
                new DisabledPasswordStore(), ProgressListener.noop).connect(session, CancelCallback.noop);
        try {
            final Path directory = new Path(remotePath, EnumSet.of(Path.Type.directory));
            final AttributedList<Path> listing = session.getFeature(ListService.class).list(directory, new DisabledListProgressListener());
            System.out.println("Connected. Listing of " + remotePath + ":");
            for(final Path child : listing) {
                System.out.println((child.isDirectory() ? "d " : "- ") + child.getName());
            }
        }
        finally {
            session.close();
        }
    }
}
