export default function SrLogo({ className }) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Strontium 로고"
    >
      {/* 몸통 — 원소 주기율표 카드 모양 */}
      <rect x="18" y="28" width="84" height="72" rx="10" fill="#e63946" />
      <rect x="22" y="32" width="76" height="64" rx="8" fill="#ff6b6b" />

      {/* 원자번호 */}
      <text
        x="30" y="50"
        fontFamily="monospace" fontSize="11" fontWeight="700"
        fill="#fff" opacity="0.85"
      >38</text>

      {/* 원소 기호 Sr */}
      <text
        x="60" y="78"
        fontFamily="monospace" fontSize="34" fontWeight="900"
        fill="#fff" textAnchor="middle" dominantBaseline="middle"
      >Sr</text>

      {/* 원소명 */}
      <text
        x="60" y="97"
        fontFamily="monospace" fontSize="9" fontWeight="600"
        fill="#ffe0e0" textAnchor="middle"
      >Strontium</text>

      {/* 눈 — 의인화 */}
      <circle cx="44" cy="53" r="5.5" fill="#fff" />
      <circle cx="76" cy="53" r="5.5" fill="#fff" />
      <circle cx="45.5" cy="54" r="2.5" fill="#1a1a2e" />
      <circle cx="77.5" cy="54" r="2.5" fill="#1a1a2e" />
      {/* 눈 반짝임 */}
      <circle cx="46.5" cy="52.5" r="1" fill="#fff" />
      <circle cx="78.5" cy="52.5" r="1" fill="#fff" />

      {/* 미소 */}
      <path
        d="M48 62 Q60 70 72 62"
        stroke="#fff" strokeWidth="2.5" strokeLinecap="round" fill="none"
      />

      {/* 팔 — 왼쪽 */}
      <path
        d="M18 70 Q8 60 12 50"
        stroke="#e63946" strokeWidth="7" strokeLinecap="round" fill="none"
      />
      {/* 손 */}
      <circle cx="11" cy="48" r="5" fill="#ff6b6b" />

      {/* 팔 — 오른쪽 */}
      <path
        d="M102 70 Q112 60 108 50"
        stroke="#e63946" strokeWidth="7" strokeLinecap="round" fill="none"
      />
      <circle cx="109" cy="48" r="5" fill="#ff6b6b" />

      {/* 다리 — 왼쪽 */}
      <path
        d="M45 100 Q42 112 38 116"
        stroke="#e63946" strokeWidth="7" strokeLinecap="round" fill="none"
      />
      {/* 다리 — 오른쪽 */}
      <path
        d="M75 100 Q78 112 82 116"
        stroke="#e63946" strokeWidth="7" strokeLinecap="round" fill="none"
      />

      {/* 전자 궤도 장식 */}
      <ellipse cx="60" cy="14" rx="18" ry="6" stroke="#ff6b6b" strokeWidth="1.5" fill="none" opacity="0.6" />
      <circle cx="78" cy="14" r="3" fill="#ffd166" />
    </svg>
  )
}
