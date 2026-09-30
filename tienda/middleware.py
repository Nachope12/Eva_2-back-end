"""
Middleware de control de errores 404.

Cualquier respuesta 404 (URL inexistente, o un registro que no existe: Http404 /
get_object_or_404) se reemplaza por:
  - páginas web  -> plantilla 404.html con la advertencia "la página no existe".
  - rutas /api/  -> JSON {"detail": "..."}.
Funciona también con DEBUG=True (donde Django normalmente mostraría su página técnica).
"""
from django.http import JsonResponse
from django.shortcuts import render


class Manejo404Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Las respuestas 404 de DRF ya son JSON: se dejan intactas.
        if response.status_code == 404 and "application/json" not in response.get("Content-Type", ""):
            if request.path.startswith("/api/"):
                return JsonResponse({"detail": "La página o recurso solicitado no existe."}, status=404)
            return render(request, "tienda/404.html", status=404)
        return response
