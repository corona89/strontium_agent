# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 스펙 — FastAPI 앱을 단일 디렉토리(onedir)로 번들.

빌드: uv run pyinstaller strontium_agent.spec --noconfirm --distpath ../api-dist
실행: api-dist/strontium_agent/strontium_agent.exe (DATA_DIR 환경변수를 주면 거기에 DB/wiki/config 생성)

주의:
- onedir 모드 — 첫 실행 시 압축 해제 비용이 없어 onefile보다 시동이 빠름.
- hiddenimports — SQLAlchemy 가 런타임에 동적 로드하는 dialect/컴포넌트들.
- limits — slowapi 가 임포트하는 패키지 누락 방지용 collect_submodules.
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    [
        "aiosqlite",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        # uvicorn[standard] 구성요소
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # bcrypt/cryptography 네이티브
        "bcrypt",
        "cryptography.fernet",
    ]
    + collect_submodules("limits")  # slowapi 의존
    + collect_submodules("sqlalchemy.dialects")  # 모든 dialect 안전망
)

a = Analysis(
    ["run_local.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="strontium_agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 디버깅용 (Electron에서 콘솔 백그라운드로 실행)
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    [],
    name="strontium_agent",
)
