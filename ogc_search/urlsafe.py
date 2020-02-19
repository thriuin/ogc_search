# -*- coding: utf-8 -*-
# -- originally contributed by Ian Ward: https://gist.github.com/wardi/fc67eeaa990ff857016726c0202118d8

import re

def url_part_escape(orig):
    """
    simple encoding for url-parts where all non-alphanumerics are
    wrapped in e.g. _xxyyzz_ blocks w/hex UTF-8 xx, yy, zz values
    used for safely including arbitrary unicode as part of a url path
    all returned characters will be in [a-zA-Z0-9_-]
    """
    return '_'.join(
        s.hex() if i % 2 else s.decode('ascii')
        for i, s in enumerate(
            re.split(b'([^-a-zA-Z0-9]+)', orig.encode('utf-8'))
        )
    )

def url_part_unescape(urlpart):
    """
    reverse url_part_escape
    """
    return ''.join(
        bytes.fromhex(s).decode('utf-8') if i % 2 else s
        for i, s in enumerate(urlpart.split('_'))
    )