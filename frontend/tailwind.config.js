module.exports = {
  content: ['./app/**/*.{ts,tsx}', './src/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: { extend: { colors: { primary: 'rgb(var(--primary) / <alpha-value>)', canvas: 'rgb(var(--canvas) / <alpha-value>)', ink: 'rgb(var(--ink) / <alpha-value>)' } } },
  plugins: [],
};
