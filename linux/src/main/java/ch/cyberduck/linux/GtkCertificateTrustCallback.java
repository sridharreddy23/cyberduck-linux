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

import ch.cyberduck.core.CertificateTrustCallback;
import ch.cyberduck.core.Controller;
import ch.cyberduck.core.exception.ConnectionCanceledException;

import org.gnome.gtk.Window;

import java.security.cert.X509Certificate;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/**
 * TLS trust prompt used by {@link ch.cyberduck.core.ssl.KeychainX509TrustManager}, the same callback
 * the Windows browser installs for untrusted certificates.
 */
public final class GtkCertificateTrustCallback implements CertificateTrustCallback {

    private final Window parent;

    public GtkCertificateTrustCallback(final Controller controller) {
        this.parent = controller instanceof LinuxController ? ((LinuxController) controller).window() : null;
    }

    @Override
    public void prompt(final String hostname, final List<X509Certificate> certificates) throws ConnectionCanceledException {
        final String subject = certificates == null || certificates.isEmpty()
                ? "The server certificate is not trusted."
                : certificates.get(0).getSubjectX500Principal().getName();
        final String message = "The identity of " + hostname + " could not be verified.\n" + subject;
        if(!GtkQuestions.ask(parent, "Certificate not trusted", message, "Continue", "Cancel")) {
            throw new ConnectionCanceledException();
        }
    }
}
