"""
Cryptographic token generation:
  1. RSA nkparam header signing (pure Python via PyCryptodome)
  2. Naukri BotGuard vid header generation (Node.js bridge)
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Optional

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from backend.core.constants import (
    BOTGUARD_APP_ID,
    BOTGUARD_PUBLIC_KEY,
    PUBLIC_KEY,
)
from backend.core.exceptions import CryptoError
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Pre-import RSA public key for nkparam
_rsa_key = RSA.import_key(PUBLIC_KEY)
_cipher = PKCS1_v1_5.new(_rsa_key)

_LOCAL_SDK_PATH = Path(__file__).parent / "botguardSdk_v1.min.js"
_FALLBACK_SDK_PATH = Path("src/utils/botguardSdk_v1.min.js")

_DRIVER_TEMPLATE = r"""
'use strict';
const fs = require('fs');

global.window = global;
global.self   = global;
global.document = {{ cookie: '' }};
try {{
    global.navigator = {{ userAgent: 'Mozilla/5.0' }};
}} catch(e) {{
    Object.defineProperty(global, 'navigator', {{
        value: {{ userAgent: 'Mozilla/5.0' }},
        writable: true, configurable: true
    }});
}}
try {{
    global.location = {{ href: 'https://www.naukri.com/nlogin/login' }};
}} catch(e) {{
    Object.defineProperty(global, 'location', {{
        value: {{ href: 'https://www.naukri.com/nlogin/login', pathname: '/nlogin/login' }},
        writable: true, configurable: true
    }});
}}
global.requirejs = function(d, cb, eb) {{ if (eb) eb(new Error('no requirejs')); }};
global.requirejs.config = function(){{}};

const sdkCode = fs.readFileSync({sdk_path!r}, 'utf8');
eval(sdkCode);

const shield = global.window.BotGuardSDK.createRequestShield({{
    appId:     {app_id!r},
    publicKey: {public_key!r},
    logger:    {{ log: function(){{}} }}
}});

shield.getDynamicToken({action!r}).then(function(vid) {{
    process.stdout.write(vid + '\n');
}}).catch(function(e) {{
    process.stderr.write('error: ' + e.message + '\n');
    process.exit(1);
}});
"""


def generate_nkparam(page_type: str = "srp") -> str:
    """
    Generates a signed `nkparam` header token for Naukri search and job detail endpoints.
    Format: v0|{timestamp_ms}|121_{page_type}
    """
    try:
        timestamp = int(time.time() * 1000)
        plaintext = f"v0|{timestamp}|121_{page_type}"
        encrypted = _cipher.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as exc:
        raise CryptoError(f"Failed to generate nkparam for {page_type}: {exc}") from exc


def generate_vid(action: str = "nlogin-login") -> str:
    """
    Generates dynamic `vid` token via BotGuard SDK using Node.js subprocess.
    """
    sdk_file = _LOCAL_SDK_PATH if _LOCAL_SDK_PATH.exists() else _FALLBACK_SDK_PATH
    if not sdk_file.exists():
        raise CryptoError(f"BotGuard SDK file not found at {sdk_file}")

    sdk_path_str = str(sdk_file.resolve()).replace("\\", "/")
    driver_script = _DRIVER_TEMPLATE.format(
        sdk_path=sdk_path_str,
        app_id=BOTGUARD_APP_ID,
        public_key=BOTGUARD_PUBLIC_KEY,
        action=action,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", delete=False, encoding="utf-8"
    ) as f:
        f.write(driver_script)
        driver_path = f.name

    try:
        result = subprocess.run(
            ["node", driver_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError as exc:
        raise CryptoError(
            "Node.js executable ('node') was not found on PATH. Node.js >=14 is required for automated login."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CryptoError("BotGuard token generation timed out after 15 seconds.") from exc
    finally:
        try:
            os.unlink(driver_path)
        except Exception:
            pass

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        raise CryptoError(f"BotGuard vid generation failed: {err}")

    vid = result.stdout.strip()
    if not vid:
        raise CryptoError("BotGuard vid generation returned empty output")

    logger.debug("Successfully generated vid (%d chars) for action=%s", len(vid), action)
    return vid
