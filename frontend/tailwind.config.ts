import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#FAFAF8',
          card: '#FFFFFF',
          primary: '#1A1A1A',
          accent: '#4A7C59',
          'accent-light': '#EBF2EE',
        },
        signal: {
          green: '#22C55E',
          yellow: '#EAB308',
          red: '#EF4444',
          'green-bg': '#F0FDF4',
          'yellow-bg': '#FEFCE8',
          'red-bg': '#FEF2F2',
        },
        rtb: {
          DEFAULT: '#3B82F6',
          light: '#EFF6FF',
          dark: '#1D4ED8',
        },
        ctb: {
          DEFAULT: '#22C55E',
          light: '#F0FDF4',
          dark: '#15803D',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px 0 rgba(0,0,0,0.04)',
        'card-hover': '0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.04)',
      },
    },
  },
  plugins: [],
}

export default config
