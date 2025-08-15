# Maio Laranja Bicas

Aplicação estática do site Maio Laranja Bicas.

## Como testar a página de desenho

1. **Clone o repositório**
   ```bash
   git clone https://github.com/danielramos222/maio-laranja-bicas
   cd maio-laranja-bicas
   ```

2. **Inicie um servidor local** (requerido para que a câmera funcione):
   - Com Python:
     ```bash
     python -m http.server 8000
     ```
   - Ou com Node.js:
     ```bash
     npx http-server . -p 8000
     ```

3. **Abra no navegador**
   ```
   http://localhost:8000/camera-desenho.html
   ```
   Pressione `C` para limpar o desenho.
