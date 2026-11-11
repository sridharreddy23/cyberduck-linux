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

import ch.cyberduck.core.Local;
import ch.cyberduck.core.LocalFactory;
import ch.cyberduck.core.preferences.ApplicationResourcesFinder;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.InputStream;
import java.net.JarURLConnection;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

/**
 * Extracts the bundled {@code *.cyberduckprofile} files (from the {@code profiles} jar) into a
 * directory {@link ch.cyberduck.core.ProtocolFactory} can scan. The official apps do the same
 * load from an installed {@code Profiles} folder.
 */
public class LinuxResourcesFinder implements ApplicationResourcesFinder {
    private static final Logger log = LogManager.getLogger(LinuxResourcesFinder.class);

    @Override
    public Local find() {
        final Path root = Path.of(System.getProperty("java.io.tmpdir"), "cyberduck-linux-resources");
        final Path profiles = root.resolve("profiles");
        try {
            Files.createDirectories(profiles);
            final URL marker = LinuxResourcesFinder.class.getClassLoader().getResource("SFTP.cyberduckprofile");
            if(marker != null && "jar".equals(marker.getProtocol())) {
                final JarURLConnection connection = (JarURLConnection) marker.openConnection();
                try(JarFile jar = connection.getJarFile()) {
                    final Enumeration<JarEntry> entries = jar.entries();
                    while(entries.hasMoreElements()) {
                        final JarEntry entry = entries.nextElement();
                        if(!entry.getName().endsWith(".cyberduckprofile") || entry.isDirectory()) {
                            continue;
                        }
                        final String name = Path.of(entry.getName()).getFileName().toString();
                        final Path out = profiles.resolve(name);
                        if(Files.exists(out) && Files.size(out) == entry.getSize()) {
                            continue;
                        }
                        try(InputStream in = jar.getInputStream(entry)) {
                            Files.copy(in, out, StandardCopyOption.REPLACE_EXISTING);
                        }
                    }
                }
            }
            else {
                log.warn("Bundled connection profiles were not found on the classpath ({})", marker);
            }
        }
        catch(final Exception e) {
            log.warn("Failed to unpack connection profiles", e);
        }
        return LocalFactory.get(root.toString());
    }
}
