#!/usr/bin/env python3
# Copyright (C) British Crown (Met Office) & Contributors.
# -----------------------------------------------------------------------------

import metomi.rose.macro


class NamelistIgnorer(metomi.rose.macro.MacroBase):

    """Test class to ignore and enable a section."""

    WARNING_ENABLED = "Enabled {0}"
    WARNING_IGNORED = "User-ignored {0}"

    def transform(self, config, meta_config=None):
        """Perform the transform operation on the section."""
        section = "namelist:ignore_nl"
        node = config.get([section])
        if node is not None:
            if node.state:
                node.state = metomi.rose.config.ConfigNode.STATE_NORMAL
                info = self.WARNING_ENABLED.format(section)
            else:
                node.state = metomi.rose.config.ConfigNode.STATE_USER_IGNORED
                info = self.WARNING_IGNORED.format(section)
        self.add_report(section, None, None, info)
        return config, self.reports
