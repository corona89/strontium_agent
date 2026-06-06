# Issue Log

## [web] Turbopack 캐시 삭제 경고

**증상**: `Turbopack's filesystem cache has been deleted because we previously detected an internal error in Turbopack.`

**원인**: 이전 Turbopack 내부 에러(루트 오탐)로 캐시가 자동 삭제됨

**해결**: 별도 조치 불필요. 루트 오탐 문제 해결 후 재실행하면 캐시 재생성되며 경고 사라짐

---

## [web] Turbopack 루트 디렉토리 오탐

**증상**: `An unexpected Turbopack error occurred.`

**원인**: `C:\Users\coron\`에 `package-lock.json`이 존재해 Turbopack이 해당 경로를 프로젝트 루트로 잘못 인식

**해결**: `web/next.config.mjs`에 루트 명시
```js
turbopack: { root: import.meta.dirname }
```

> `.mjs`(ES 모듈)에서는 `__dirname` 미지원 → `import.meta.dirname` 사용 (Node.js 21.2+)
