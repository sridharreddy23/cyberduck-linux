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
import ch.cyberduck.core.Scheme;

import org.apache.commons.lang3.StringUtils;

import java.util.List;

/**
 * Connection-dialog choices. Same set the Mac and Windows apps show: every enabled bundled
 * profile registered through {@link ProtocolFactory}, not a hand-picked subset.
 */
final class ProtocolChoice {

    private ProtocolChoice() {
    }

    static List<Protocol> choices() {
        final List<Protocol> enabled = ProtocolFactory.get().find(Protocol::isEnabled);
        if(!enabled.isEmpty()) {
            return enabled;
        }
        return ProtocolFactory.get().find(protocol -> true);
    }

    static String[] labels() {
        return choices().stream().map(ProtocolChoice::label).toArray(String[]::new);
    }

    static int defaultIndex() {
        final List<Protocol> protocols = choices();
        for(int i = 0; i < protocols.size(); i++) {
            if(Scheme.sftp.equals(protocols.get(i).getScheme())) {
                return i;
            }
        }
        return 0;
    }

    static Protocol get(final int index) {
        final List<Protocol> protocols = choices();
        if(protocols.isEmpty()) {
            throw new IllegalStateException("No protocols are registered");
        }
        final int safe = Math.min(Math.max(index, 0), protocols.size() - 1);
        return protocols.get(safe);
    }

    private static String label(final Protocol protocol) {
        if(StringUtils.isNotBlank(protocol.getDescription())) {
            return protocol.getDescription();
        }
        return protocol.getName();
    }
}
