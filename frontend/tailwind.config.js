/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0d1117',
        'ink-soft': '#151c24',
        'ink-card': '#1a222c',
        line: '#28323e',
        'line-hi': '#39465a',
        txt: '#dbe4ee',
        'txt-dim': '#8595a8',
        'txt-mute': '#5c6b7d',
        signal: '#3ecf8e',
        'signal-dim': 'rgba(62,207,142,.14)',
        amber: '#f0b429',
        'amber-dim': 'rgba(240,180,41,.14)',
        red: '#f0616d',
        'red-dim': 'rgba(240,97,109,.14)',
        blue: '#5aa9f7',
        'blue-dim': 'rgba(90,169,247,.14)',
        violet: '#a78bfa',
        'violet-dim': 'rgba(167,139,250,.14)',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      keyframes: {
        fade: {
          from: { opacity: 0, transform: 'translateY(6px)' },
          to: { opacity: 1, transform: 'none' },
        },
        sweep: {
          from: { transform: 'rotate(190deg)' },
          to: { transform: 'rotate(550deg)' },
        },
        blip: {
          '0%, 70%': { opacity: 0 },
          '80%': { opacity: 1 },
          '100%': { opacity: 0.25 },
        },
        typingDot: {
          '0%, 60%, 100%': { transform: 'none', opacity: 0.4 },
          '30%': { transform: 'translateY(-4px)', opacity: 1 },
        },
      },
      animation: {
        fade: 'fade .25s ease',
        sweep: 'sweep 3.4s linear infinite',
        blip: 'blip 3.4s ease-in-out infinite',
        'typing-dot': 'typingDot 1s infinite',
      },
    },
  },
  plugins: [],
}
