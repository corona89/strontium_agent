// Electron main process — FastAPI(PyInstaller) + Next.js standalone 을 자식으로 띄우고,
// 부트스트랩 토큰을 받아 BrowserWindow 에 쿠키로 주입한 뒤 UI를 로드한다.
//
// 환경변수:
//   SA_DEV=1        개발 모드 — 번들된 빌드 대신 api/ · web/ 을 직접 실행 (yarn dev / uv run uvicorn)
//   SA_API_PORT     기본 8000
//   SA_WEB_PORT     기본 3000

const {
  app,
  BrowserWindow,
  session,
  Menu,
  shell,
  dialog,
  powerMonitor,
} = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");
const os = require("os");

const IS_DEV = !!process.env.SA_DEV;
const API_PORT = parseInt(process.env.SA_API_PORT || "8000", 10);
const WEB_PORT = parseInt(process.env.SA_WEB_PORT || "3000", 10);
const API_BASE = `http://127.0.0.1:${API_PORT}`;
const WEB_BASE = `http://127.0.0.1:${WEB_PORT}`;

// 사용자 데이터 디렉토리 — FastAPI 가 DATA_DIR 환경변수로 받아 DB/wiki/config 저장
const DATA_DIR = path.join(
  app.getPath("userData"),
  "data"
);

let apiProcess = null;
let webProcess = null;
let mainWindow = null;
let splashWindow = null;
let isQuitting = false;

// ---------------------------------------------------------------------------
// 자식 프로세스 관리
// ---------------------------------------------------------------------------

function getResourcePath(...segments) {
  // production: process.resourcesPath 에 api-dist/, web-out/ 이 해제됨
  // dev: 모노레포 루트의 api/, web/ 을 그대로 사용
  if (IS_DEV) {
    const repoRoot = path.resolve(__dirname, "..");
    return path.join(repoRoot, ...segments);
  }
  return path.join(process.resourcesPath, ...segments);
}

function spawnApi() {
  const env = {
    ...process.env,
    DATA_DIR,
    LOCAL_MODE: "true",
    PYTHONUNBUFFERED: "1",
  };

  if (IS_DEV) {
    // 개발 모드: uv run uvicorn 으로 직접 실행
    const apiDir = getResourcePath("api");
    return spawn(
      "uv",
      ["run", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(API_PORT)],
      { cwd: apiDir, env, shell: true, windowsHide: true }
    );
  }

  const exeDir = getResourcePath("api-dist", "strontium_agent");
  const exeName = process.platform === "win32" ? "strontium_agent.exe" : "strontium_agent";
  return spawn(path.join(exeDir, exeName), [], {
    cwd: exeDir,
    env,
    windowsHide: true,
  });
}

function spawnWeb() {
  const env = {
    ...process.env,
    NODE_ENV: "production",
    HOSTNAME: "127.0.0.1",
    PORT: String(WEB_PORT),
    // Next standalone server 가 읽는 NEXT_PUBLIC_API_URL 은 런타임 env-config.js 로 주입
    NEXT_PUBLIC_API_URL: API_BASE,
  };

  if (IS_DEV) {
    // 개발 모드: yarn dev (포트 충돌 회피용으로 그대로 3000 사용)
    const webDir = getResourcePath("web");
    const cmd = process.platform === "win32" ? "yarn.cmd" : "yarn";
    return spawn(cmd, ["dev"], { cwd: webDir, env, shell: true });
  }

  const webDir = getResourcePath("web-out");
  // process.execPath 는 패키징 시 'Strontium Agent.exe' (경로에 'electron' 없음).
  // ELECTRON_RUN_AS_NODE=1 없이 실행하면 앱 전체(main.js)가 재실행되어
  // fork bomb 가 된다. 이 플래그를 주면 Electron 바이너리가 순수 Node.js 로
  // 동작해 server.js 를 정상 실행한다. (별도 node.exe 번들 불필요)
  return spawn(process.execPath, ["server.js"], {
    cwd: webDir,
    env: { ...env, ELECTRON_RUN_AS_NODE: "1" },
    windowsHide: true,
  });
}

function attachProcess(proc, label) {
  if (!proc) return;
  proc.on("error", (err) => console.error(`[${label}] spawn error:`, err));
  proc.stdout.on("data", (d) => process.stdout.write(`[${label}] ${d}`));
  proc.stderr.on("data", (d) => process.stderr.write(`[${label}] ${d}`));
  proc.on("exit", (code) => {
    console.log(`[${label}] exited with code ${code}`);
    if (!isQuitting && code !== 0 && mainWindow) {
      showErrorThenQuit(`${label} 프로세스가 예기치 않게 종료되었습니다 (code ${code}).`);
    }
  });
}

function killProcess(proc) {
  if (!proc || proc.exitCode !== null) return Promise.resolve();
  return new Promise((resolve) => {
    proc.once("exit", resolve);
    if (process.platform === "win32") {
      // 자식 트리 전체 종료 (uv → uvicorn, yarn → node 등)
      try {
        require("child_process").execSync(
          `taskkill /pid ${proc.pid} /T /F`,
          { stdio: "ignore" }
        );
      } catch {
        proc.kill();
      }
    } else {
      proc.kill("SIGTERM");
    }
    setTimeout(resolve, 3000); // 안전망
  });
}

// ---------------------------------------------------------------------------
// 헬스체크
// ---------------------------------------------------------------------------

function pollUrl(url, { timeoutMs = 60000, intervalMs = 300 } = {}) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) {
          resolve();
        } else if (Date.now() - start > timeoutMs) {
          reject(new Error(`timeout waiting for ${url}`));
        } else {
          setTimeout(tryOnce, intervalMs);
        }
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`timeout waiting for ${url}`));
        } else {
          setTimeout(tryOnce, intervalMs);
        }
      });
      req.setTimeout(2000, () => req.destroy(new Error("socket timeout")));
    };
    tryOnce();
  });
}

// ---------------------------------------------------------------------------
// 부트스트랩 (자동 로그인)
// ---------------------------------------------------------------------------

async function fetchBootstrapTokens() {
  // 서버 시작 직후 seed_local_admin 이 완료되지 않았을 수 있어 409면 재시도
  const maxAttempts = 20;
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const resp = await fetch(`${API_BASE}/local/bootstrap`, { method: "POST" });
      if (resp.ok) return await resp.json();
      if (resp.status !== 409) {
        throw new Error(`bootstrap failed: HTTP ${resp.status}`);
      }
    } catch (e) {
      if (i === maxAttempts - 1) throw e;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("bootstrap: max retries exceeded");
}

async function injectCookies(tokens) {
  const cookieOpts = {
    url: WEB_BASE,
    httpOnly: true,
    secure: false,
    sameSite: "lax",
  };
  await session.defaultSession.cookies.set({
    ...cookieOpts,
    name: "access_token",
    value: tokens.access_token,
    expirationDate: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 7,
  });
  await session.defaultSession.cookies.set({
    ...cookieOpts,
    name: "refresh_token",
    value: tokens.refresh_token,
    expirationDate: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 7,
  });
}

// ---------------------------------------------------------------------------
// 창 관리
// ---------------------------------------------------------------------------

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    resizable: false,
    movable: false,
    center: true,
    show: true,
    backgroundColor: "#0f172a",
    webPreferences: { contextIsolation: true },
  });
  splashWindow.loadFile(path.join(__dirname, "splash.html"));
}

function showErrorThenQuit(message) {
  dialog.showErrorBox("Strontium Agent", message);
  app.quit();
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 600,
    show: false,
    backgroundColor: "#0f172a",
    title: "Strontium Agent",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 외부 링크는 시스템 브라우저로
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://127.0.0.1") || url.startsWith("http://localhost")) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.once("ready-to-show", () => {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  mainWindow.loadURL(WEB_BASE);
}

// ---------------------------------------------------------------------------
// 라이프사이클
// ---------------------------------------------------------------------------

async function bootstrap() {
  // DATA_DIR 미리 생성 (FastAPI 도 만들지만 동시성 안전망)
  fs.mkdirSync(DATA_DIR, { recursive: true });

  apiProcess = spawnApi();
  attachProcess(apiProcess, "api");

  // Next 는 API 보다 늦게 띄워도 됨 — 병렬 spawn
  webProcess = spawnWeb();
  attachProcess(webProcess, "web");

  try {
    await Promise.all([
      pollUrl(`${API_BASE}/`),
      pollUrl(`${WEB_BASE}/`),
    ]);
  } catch (e) {
    showErrorThenQuit(
      `서버 기동에 실패했습니다.\n${e.message}\n\n` +
        `포트 ${API_PORT} 또는 ${WEB_PORT}이(가) 사용 중인지 확인하세요.`
    );
    return;
  }

  try {
    const tokens = await fetchBootstrapTokens();
    await injectCookies(tokens);
  } catch (e) {
    console.error("bootstrap failed:", e);
    showErrorThenQuit(`자동 로그인에 실패했습니다.\n${e.message}`);
    return;
  }

  createMainWindow();
}

app.whenReady().then(() => {
  // 개발 중엔 메뉴 유지, 프로덕션은 단순화
  if (!IS_DEV) {
    Menu.setApplicationMenu(null);
  }
  createSplash();
  bootstrap();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", async (e) => {
  isQuitting = true;
  e.preventDefault();
  await Promise.all([killProcess(apiProcess), killProcess(webProcess)]);
  apiProcess = null;
  webProcess = null;
  app.exit(0);
});

// 윈도우 잠금/절전 시 자식 프로세스 그대로 유지 (DB 일관성 보호)
powerMonitor.on("suspend", () => console.log("system suspending"));
powerMonitor.on("resume", () => console.log("system resumed"));
