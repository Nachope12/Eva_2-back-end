# TechHardware - EVA-2 Backend (Proyecto 1: Tienda de Hardware y Componentes PC)

Django REST Framework + PostgreSQL + JWT (claims de rol) + django-filter + drf-spectacular.

## Puesta en marcha
    python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    docker compose up -d                                  # o use su PostgreSQL local (variables DB_* en settings.py)
    python manage.py makemigrations tienda
    python manage.py migrate
    python manage.py cargar_datos                         # datos de prueba
    python manage.py runserver

Antes de entregar: edite ALUMNO_NOMBRE, ALUMNO_SECCION y ALUMNO_ANIO en tienda_hardware/settings.py.

## Páginas HTML (templates) y control de 404
- Público: /catalogo/ (filtros), /catalogo/{id}/, /login/, /registro/
- Cliente: /carro/, /mis-ordenes/, /mis-ordenes/{id}/ (agregar / modificar / eliminar ítems, checkout, pagar)
- Administrador: /panel/categorias/, /panel/productos/ (CRUD completo), /panel/ordenes/ (cambio de estado)
- Cualquier URL o registro inexistente muestra la advertencia `404.html` (middleware `tienda/middleware.py` + `handler404`); rutas /api/ responden JSON 404. Sin permiso: `403.html`.

## URLs
- Home (con footer del alumno): http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/api/docs/

## Roles del sistema
| Rol | Puede |
|-----|-------|
| **SUPERADMIN** | Todo: CRUD completo de catálogo (incluye eliminar), cambiar cualquier estado de orden (PAGADO / ENTREGADO / CANCELADO, mueven inventario), y CRUD de usuarios y roles. |
| **ADMINISTRADOR** | Crear y editar categorías/productos (no eliminar), ver todas las órdenes y marcarlas solo como ENTREGADO. No gestiona usuarios ni mueve inventario (PAGADO/CANCELADO). |
| **CLIENTE (usuario)** | Solo ver el catálogo público, usar su carro persistente y comprar (checkout / pagar). No entra al panel de gestión. |

## Usuarios de prueba
| Usuario  | Clave         | Rol            |
|----------|---------------|----------------|
| admin    | Admin12345!   | SUPERADMIN     |
| gestor   | Gestor12345!  | ADMINISTRADOR  |
| cliente  | Cliente12345! | CLIENTE        |
| cliente2 | Cliente12345! | CLIENTE        |
| nacho    | 12345         | CLIENTE        |

Estos usuarios los crea `python manage.py cargar_datos` y quedan disponibles después de correr el proyecto.

## Actualización de inventario al comprar
`POST /api/ordenes/checkout/` acepta `{"pagar": true|false}`:
- `pagar: true` (o el botón **"Comprar ahora"** en `/carro/`): checkout + pago en una sola transacción atómica. La orden queda **PAGADO** y el **stock se descuenta al instante** (o se rechaza todo si falta inventario).
- `pagar: false` (o **"Generar orden pendiente"**): solo crea la orden **PENDIENTE**; el stock se actualiza recién cuando alguien la paga (`POST /api/ordenes/{id}/pagar/` o el SUPERADMIN vía `PATCH /estado/`).

## Solución si PostgreSQL no responde (Windows)
Si al correr el proyecto aparece `psycopg2.OperationalError: Connection refused (0x0000274D/10061)`, es porque el servicio de PostgreSQL no está corriendo o no acepta conexiones en el puerto 5432:

1. **Iniciar el servicio de PostgreSQL en Windows**
   - *Interfaz gráfica:* `Win + R` → `services.msc` → Enter. Busca `postgresql-x64-XX` (XX = tu versión) → clic derecho → **Iniciar** (o **Reiniciar**).
   - *PowerShell (como Administrador):*
     ```powershell
     Start-Service postgresql-x64-*
     ```
2. **Verificar la base de datos en `settings.py`** — el nombre, usuario, clave, host y puerto deben coincidir con tu instalación:
   Este proyecto ya viene configurado (en `tienda_hardware/settings.py`) para usar:
   ```python
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.postgresql",
           "NAME": "tienda_hardware_db",
           "USER": "postgres",
           "PASSWORD": "12345",
           "HOST": "localhost",
           "PORT": "5432",
       }
   }
   ```
   Si la base de datos aún no existe, créala desde pgAdmin o `psql`:
   ```sql
   CREATE DATABASE tienda_hardware_db
       WITH
       OWNER = postgres
       ENCODING = 'UTF8'
       LOCALE_PROVIDER = 'libc'
       CONNECTION LIMIT = -1
       IS_TEMPLATE = False;
   ```
   Y que la clave del usuario `postgres` en tu instalación sea `12345` (o ajusta `PASSWORD` en `settings.py` a la que corresponda).
3. **Volver a correr el proyecto**: `python manage.py migrate` y luego `python manage.py runserver`.

## Flujo
1. POST /api/auth/login/  -> access + refresh (claims: rol, username)
2. POST /api/carro/  {"producto_id": 1, "cantidad": 2}
3. POST /api/ordenes/checkout/  -> Orden PENDIENTE (precios congelados, carro vaciado)
4. POST /api/ordenes/{id}/pagar/  (cliente)  o  PATCH /api/ordenes/{id}/estado/ {"estado":"PAGADO"} (admin)
   -> valida stock y lo descuenta atomicamente
5. PATCH /api/ordenes/{id}/estado/ {"estado":"CANCELADO"} -> repone stock; {"estado":"ENTREGADO"} -> cierra
