# Enmarcador para Instagram

App FastAPI + HTMX para preparar publicaciones de obras de arte para Instagram.

## Uso local

```bash
just start
```

Abrir:

```text
http://127.0.0.1:8000
```

## Flujo

1. Subir imágenes de la obra.
2. Indicar técnica/material y medidas.
3. Generar imágenes cuadradas `2000x2000` y un caption en español.
4. Revisar el preview.
5. Reordenar las imágenes del carrusel arrastrándolas.
6. Descargar el ZIP o publicar manualmente en Instagram.

## Variables de entorno

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...
PUBLIC_BASE_URL=https://...
FRAME_BACKGROUND=#f7f3ea
FRAME_SHADOW_OPACITY=0.22
MAX_UPLOAD_COUNT=10
MAX_UPLOAD_MB=50
MAX_OUTPUT_MB=8
GENERATED_TTL_SECONDS=3600
```

`PUBLIC_BASE_URL` debe ser una URL pública para que Instagram pueda descargar las imágenes generadas.

## Comandos

```bash
just start
just test
just check
```

## TODO

- Probar publicación real con credenciales finales de Instagram/Meta.
- Confirmar permisos requeridos en Meta App Review para la cuenta final.
- Mejorar persistencia de trabajos si la app se usa con múltiples instancias o reinicios.
- Considerar S3/R2 si Instagram no descarga de forma confiable desde almacenamiento temporal local.
- Añadir edición manual del caption antes de publicar.
