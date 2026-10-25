// Estilos de la aplicacion (direccion B, ver ../.21st/design.json). Compilar con:
//   npx tailwindcss@3.4.16 -i estilos/app.css -o se_app/presentacion/static/css/app.css --minify
module.exports = {
  content: ["./se_app/**/*.html", "./se_app/**/*.py"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
};
