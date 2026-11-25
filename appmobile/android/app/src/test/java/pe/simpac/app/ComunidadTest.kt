package pe.simpac.app

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AuthSupabase
import pe.simpac.app.data.ComunidadSupabase
import pe.simpac.app.data.ErrorAuth
import pe.simpac.app.data.ErrorConsulta
import pe.simpac.app.data.JsonSifec
import pe.simpac.app.data.PeticionHttp
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.data.RespuestaHttp
import pe.simpac.app.data.SesionGuardada
import pe.simpac.app.data.TransporteHttp
import pe.simpac.app.dominio.Comunidad

/** Transporte simulado: guarda lo que recibio y responde lo que la prueba diga. Sin red. */
private class TransporteFalso(private val respuestas: List<RespuestaHttp>) : TransporteHttp {
    val enviadas = mutableListOf<PeticionHttp>()
    override suspend fun enviar(p: PeticionHttp): RespuestaHttp {
        enviadas += p
        return respuestas.getOrElse(enviadas.size - 1) { respuestas.last() }
    }
}

private const val URL = "https://proyecto.supabase.co"
private const val CLAVE = "sb_publishable_prueba"
private const val TOKEN = "jwt-de-prueba"
private const val UID = "5f6a1c6e-9a5b-4d1e-8f2c-3b4a5c6d7e8f"

/** Comunidad y cuentas nativas: logica pura, armado de peticiones y parseo de Auth (sin red). */
class ComunidadTest {
    private fun reporte(id: String, confianza: Double? = 0.5, lat: Double? = -7.16, lon: Double? = -78.51, creado: String = "2026-11-19T10:00:00+00:00", expira: String = "2026-11-19T22:00:00+00:00") =
        ReporteVigente(id = id, tipo = "inundacion", confianza = confianza, lat = lat, lon = lon, creado_en = creado, expira_en = expira)

    // ---- orden por confianza y distancia ----
    @Test
    fun ordena_por_confianza_y_castiga_la_lejania() {
        val cerca = reporte("cerca", confianza = 0.5, lat = -7.16, lon = -78.51)
        val lejosPeroConfiable = reporte("lejos", confianza = 0.9, lat = -12.05, lon = -77.04)   // Lima: ~560 km, castigo tope 2
        val sinPos = reporte("sinpos", confianza = 0.6, lat = null, lon = null)                   // sin castigo
        val lista = Comunidad.ordenar(listOf(lejosPeroConfiable, cerca, sinPos), -7.16, -78.51)
        assertEquals(listOf("sinpos", "cerca", "lejos"), lista.map { it.reporte.id })
        assertEquals(0.0, lista[1].distanciaKm!!, 0.01)
        assertEquals(0.9 - 2.0, lista[2].puntaje, 1e-9)
    }

    @Test
    fun sin_posicion_solo_cuenta_la_confianza_y_el_empate_lo_gana_el_mas_nuevo() {
        val viejo = reporte("viejo", confianza = 0.5, creado = "2026-11-19T08:00:00+00:00")
        val nuevo = reporte("nuevo", confianza = 0.5, creado = "2026-11-19T11:00:00+00:00")
        val mejor = reporte("mejor", confianza = 0.7, creado = "2026-11-19T07:00:00+00:00")
        val lista = Comunidad.ordenar(listOf(viejo, nuevo, mejor), null, null)
        assertEquals(listOf("mejor", "nuevo", "viejo"), lista.map { it.reporte.id })
        assertTrue(lista.all { it.distanciaKm == null })
    }

    @Test
    fun textos_de_distancia_y_vencimiento() {
        assertEquals("a 350 m", Comunidad.textoDistancia(0.35))
        assertEquals("a 10 m", Comunidad.textoDistancia(0.001))
        assertEquals("a 1,2 km", Comunidad.textoDistancia(1.24))
        assertEquals("a 15 km", Comunidad.textoDistancia(15.4))
        assertNull(Comunidad.textoDistancia(null))
        val ahora = 1_800_000_000_000L
        fun iso(ms: Long) = java.time.Instant.ofEpochMilli(ms).toString()
        assertEquals("vence en 45 min", Comunidad.venceEn(iso(ahora + 45 * 60_000), ahora))
        assertEquals("vence en 1 h 20 min", Comunidad.venceEn(iso(ahora + 80 * 60_000), ahora))
        assertEquals("vence en 2 h", Comunidad.venceEn(iso(ahora + 120 * 60_000), ahora))
        assertEquals("vence en 2 días", Comunidad.venceEn(iso(ahora + 50 * 3_600_000), ahora))
        assertEquals("vencido", Comunidad.venceEn(iso(ahora - 1), ahora))
        assertEquals("Atasco detenido", Comunidad.nombreReporte("atasco", "detenido"))
        assertEquals("Inundación", Comunidad.nombreReporte("inundacion", null))
        assertEquals("Otro", Comunidad.nombreReporte("algo_raro", null))
    }

    // ---- validaciones del formulario ----
    @Test
    fun valida_el_reporte_como_la_web() {
        assertTrue(Comunidad.validarReporte("inundacion", null, "calle anegada", -7.16, -78.51).isEmpty())
        assertEquals("Elige qué estás viendo.", Comunidad.validarReporte(null, null, "", -7.16, -78.51)["tipo"])
        assertEquals("Indica qué tan fuerte es el atasco.", Comunidad.validarReporte("atasco", null, "", -7.16, -78.51)["subtipo"])
        assertTrue(Comunidad.validarReporte("atasco", "leve", "", -7.16, -78.51).isEmpty())
        assertEquals("Ese detalle no corresponde a este tipo de reporte.", Comunidad.validarReporte("bache", "leve", "", -7.16, -78.51)["subtipo"])
        assertEquals("No tenemos tu ubicación. Sin ella no se puede reportar.", Comunidad.validarReporte("bache", null, "", null, null)["pos"])
        assertEquals("Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.", Comunidad.validarReporte("bache", null, "", 40.4, -3.7)["pos"])
        val larga = "x".repeat(501)
        assertEquals("La descripción puede tener hasta 500 letras (llevas 501).", Comunidad.validarReporte("bache", null, larga, -7.16, -78.51)["descripcion"])
        assertEquals("SRID=4326;POINT(-78.51 -7.16)", Comunidad.ewkt(-7.16, -78.51))
    }

    @Test
    fun valida_la_cuenta_y_el_comentario() {
        assertEquals("Escribe un correo válido.", Comunidad.validarCuenta("sin-arroba", "123456")["email"])
        assertEquals("La contraseña tiene que tener al menos 6 caracteres.", Comunidad.validarCuenta("a@b.pe", "123")["password"])
        assertEquals("Escribe el nombre con el que quieres aparecer.", Comunidad.validarCuenta("a@b.pe", "123456", "R", conNombre = true)["nombre"])
        assertTrue(Comunidad.validarCuenta(" rosa@correo.pe ", "123456", "Rosa", conNombre = true).isEmpty())
        assertEquals(null to "Escribe algo antes de enviar.", Comunidad.validarTexto("   "))
        assertEquals("hola" to null, Comunidad.validarTexto("  hola "))
        assertEquals(null to "Puede tener hasta 500 letras (llevas 501).", Comunidad.validarTexto("y".repeat(501)))
    }

    // ---- errores en lenguaje claro ----
    @Test
    fun traduce_los_errores_de_la_bd() {
        assertEquals("Llegaste al límite de 5 por hora. Espera un rato antes de volver a enviar el reporte.",
            Comunidad.mensajeErrorBD(400, """{"code":"P0001","message":"límite de 5 por hora alcanzado"}""", "enviar el reporte"))
        assertEquals("No puedes votar tu propio reporte.", Comunidad.mensajeErrorBD(400, """{"message":"no se puede votar el propio reporte"}""", "votar"))
        assertEquals("Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.",
            Comunidad.mensajeErrorBD(400, """{"code":"23514","message":"new row for relation \"report\" violates check constraint \"report_geom_check\""}"""))
        assertEquals(Comunidad.SESION_VENCIDA, Comunidad.mensajeErrorBD(401, """{"code":"PGRST301","message":"JWT expired"}"""))
        assertEquals("La foto pesa demasiado (máximo 3 MB).", Comunidad.mensajeErrorBD(413, """{"statusCode":"413","error":"Payload too large","message":"The object exceeded the maximum allowed size"}""", "subir la foto"))
        assertEquals("La foto tiene que ser JPG, PNG o WebP.", Comunidad.mensajeErrorBD(415, """{"statusCode":"415","error":"invalid_mime_type","message":"mime type text/plain is not supported"}"""))
        assertEquals("Este reporte ya venció: no admite votos ni comentarios.", Comunidad.mensajeErrorBD(400, """{"message":"solo sobre reportes vigentes"}"""))
        assertEquals("No se pudo comentar. Inténtalo de nuevo en un momento.", Comunidad.mensajeErrorBD(500, "no es json", "comentar"))
    }

    @Test
    fun traduce_los_errores_de_auth() {
        assertEquals("Correo o contraseña incorrectos.", Comunidad.mensajeAuth(400, """{"code":400,"error_code":"invalid_credentials","msg":"Invalid login credentials"}"""))
        assertEquals("Correo o contraseña incorrectos.", Comunidad.mensajeAuth(400, """{"error":"invalid_grant","error_description":"Invalid login credentials"}"""))
        assertEquals("Tu correo aún no está confirmado. Busca el mensaje que te enviamos (revisa también la carpeta de spam).", Comunidad.mensajeAuth(400, """{"error_code":"email_not_confirmed","msg":"Email not confirmed"}"""))
        assertEquals("Ya hay una cuenta con ese correo. Entra con tu contraseña o pide una nueva.", Comunidad.mensajeAuth(422, """{"error_code":"user_already_exists","msg":"User already registered"}"""))
        assertEquals("La contraseña tiene que tener al menos 6 caracteres.", Comunidad.mensajeAuth(422, """{"error_code":"weak_password","msg":"Password should be at least 6 characters."}"""))
        assertEquals("Enviamos demasiados correos en poco tiempo. Espera unos minutos y vuelve a intentar.", Comunidad.mensajeAuth(429, """{"error_code":"over_email_send_rate_limit","msg":"email rate limit exceeded"}"""))
        assertEquals("Ese correo no parece válido. Revísalo.", Comunidad.mensajeAuth(400, """{"error_code":"validation_failed","msg":"Unable to validate email address: invalid format"}"""))
        assertEquals(Comunidad.SESION_VENCIDA, Comunidad.mensajeAuth(400, """{"error_code":"refresh_token_not_found","msg":"Invalid Refresh Token: Refresh Token Not Found"}"""))
        assertEquals("No se pudo completar. Inténtalo de nuevo en un momento.", Comunidad.mensajeAuth(500, ""))
    }

    // ---- peticiones de Auth (cuerpos y cabeceras) ----
    @Test
    fun arma_las_peticiones_de_auth() {
        val auth = AuthSupabase(URL, CLAVE)
        val entrar = auth.peticionEntrar(" rosa@correo.pe ", "secreta1")
        assertEquals("POST", entrar.metodo)
        assertEquals("$URL/auth/v1/token?grant_type=password", entrar.url)
        assertEquals(CLAVE, entrar.cabeceras["apikey"])
        assertEquals("Bearer $CLAVE", entrar.cabeceras["Authorization"])
        assertEquals("application/json", entrar.cabeceras["Content-Type"])
        val cuerpo = JsonSifec.parseToJsonElement(entrar.cuerpoTexto!!).jsonObject
        assertEquals("rosa@correo.pe", cuerpo["email"]!!.jsonPrimitive.content)
        assertEquals("secreta1", cuerpo["password"]!!.jsonPrimitive.content)

        val registro = auth.peticionRegistro("rosa@correo.pe", "secreta1", " Rosa ", "https://sifec.example/cuenta")
        assertEquals("$URL/auth/v1/signup?redirect_to=https%3A%2F%2Fsifec.example%2Fcuenta", registro.url)
        val datos = JsonSifec.parseToJsonElement(registro.cuerpoTexto!!).jsonObject
        assertEquals("Rosa", datos["data"]!!.jsonObject["nombre"]!!.jsonPrimitive.content)
        assertEquals(setOf("email", "password", "data"), datos.keys)   // nada mas que correo, contrasena y nombre

        val refrescar = auth.peticionRefrescar("rt-1")
        assertEquals("$URL/auth/v1/token?grant_type=refresh_token", refrescar.url)
        assertEquals("""{"refresh_token":"rt-1"}""", refrescar.cuerpoTexto)

        val recuperar = auth.peticionRecuperar("rosa@correo.pe", "https://sifec.example/cuenta")
        assertEquals("$URL/auth/v1/recover?redirect_to=https%3A%2F%2Fsifec.example%2Fcuenta", recuperar.url)
        assertEquals("""{"email":"rosa@correo.pe"}""", recuperar.cuerpoTexto)

        val salir = auth.peticionSalir(TOKEN)
        assertEquals("$URL/auth/v1/logout", salir.url)
        assertEquals("Bearer $TOKEN", salir.cabeceras["Authorization"])
        assertEquals("GET", auth.peticionUsuario(TOKEN).metodo)
    }

    @Test
    fun parsea_la_respuesta_de_auth() {
        val cuerpo = """{"access_token":"$TOKEN","token_type":"bearer","expires_in":3600,"expires_at":1800003600,"refresh_token":"rt-1",
            "user":{"id":"$UID","aud":"authenticated","email":"rosa@correo.pe","user_metadata":{"nombre":"Rosa","email_verified":true},"identities":[{"id":"x"}]}}"""
        val s = AuthSupabase.parsearSesion(cuerpo, ahoraSeg = 1800000000)
        assertNotNull(s)
        assertEquals(TOKEN, s!!.accessToken)
        assertEquals("rt-1", s.refreshToken)
        assertEquals(1800003600L, s.expiraEnSeg)
        assertEquals(UID, s.usuarioId)
        assertEquals("rosa@correo.pe", s.email)
        assertEquals("Rosa", s.nombre)
        assertFalse(s.porVencer(ahoraSeg = 1800000000))
        assertTrue(s.porVencer(ahoraSeg = 1800003590))
        // ida y vuelta por el almacen cifrado
        assertEquals(s, SesionGuardada.desdeJson(s.aJson()))
        assertNull(SesionGuardada.desdeJson("basura"))
        // sin expires_at: se calcula con expires_in
        val sinExpiraEn = AuthSupabase.parsearSesion("""{"access_token":"a","refresh_token":"r","expires_in":100,"user":{"id":"$UID"}}""", ahoraSeg = 50)
        assertEquals(150L, sinExpiraEn!!.expiraEnSeg)
        assertNull(sinExpiraEn.nombre)
        // un usuario sin sesion (registro con confirmacion por correo) no es una sesion
        assertNull(AuthSupabase.parsearSesion("""{"id":"$UID","email":"rosa@correo.pe","identities":[]}"""))
    }

    @Test
    fun entrar_y_registrar_con_transporte_simulado() = runTest {
        val sesionJson = """{"access_token":"$TOKEN","refresh_token":"rt","expires_at":1900000000,"user":{"id":"$UID","email":"rosa@correo.pe","user_metadata":{"nombre":"Rosa"}}}"""
        val t = TransporteFalso(listOf(RespuestaHttp(200, sesionJson)))
        val auth = AuthSupabase(URL, CLAVE, t)
        val s = auth.entrar("rosa@correo.pe", "secreta1")
        assertEquals(UID, s.usuarioId)
        assertEquals("$URL/auth/v1/token?grant_type=password", t.enviadas.single().url)

        // registro con confirmacion por correo: usuario sin sesion
        val t2 = TransporteFalso(listOf(RespuestaHttp(200, """{"id":"$UID","email":"rosa@correo.pe","identities":[{"id":"i1"}]}""")))
        val r = AuthSupabase(URL, CLAVE, t2).registrar("rosa@correo.pe", "secreta1", "Rosa", "https://sifec.example/cuenta")
        assertNull(r.sesion)
        assertTrue(r.confirmar)
        assertFalse(r.yaExistia)
        // correo que ya existia: identidades vacias
        val t3 = TransporteFalso(listOf(RespuestaHttp(200, """{"id":"$UID","email":"rosa@correo.pe","identities":[]}""")))
        assertTrue(AuthSupabase(URL, CLAVE, t3).registrar("rosa@correo.pe", "secreta1", "Rosa", "https://sifec.example/cuenta").yaExistia)
        // credenciales malas: ErrorAuth con el mensaje claro y el codigo
        val t4 = TransporteFalso(listOf(RespuestaHttp(400, """{"error_code":"invalid_credentials","msg":"Invalid login credentials"}""")))
        try {
            AuthSupabase(URL, CLAVE, t4).entrar("rosa@correo.pe", "mala")
            assertTrue("debia fallar", false)
        } catch (e: ErrorAuth) {
            assertEquals("Correo o contraseña incorrectos.", e.message)
            assertEquals(400, e.codigoHttp)
        }
    }

    // ---- peticiones de la comunidad (cuerpos y cabeceras) ----
    private fun comunidad(t: TransporteHttp = TransporteFalso(listOf(RespuestaHttp(200, "[]"))), token: String? = TOKEN) =
        ComunidadSupabase(URL, CLAVE, t) { token }

    @Test
    fun arma_la_peticion_de_crear_reporte() {
        val p = comunidad().peticionCrearReporte(TOKEN, "atasco", "leve", "  pista anegada ", null, -7.16, -78.51)
        assertEquals("POST", p.metodo)
        assertEquals("$URL/rest/v1/report?select=${ComunidadSupabase.COLS_REPORTE.replace(",", "%2C")}", p.url)
        assertEquals(CLAVE, p.cabeceras["apikey"])
        assertEquals("Bearer $TOKEN", p.cabeceras["Authorization"])
        assertEquals("return=representation", p.cabeceras["Prefer"])
        assertEquals("application/json", p.cabeceras["Content-Type"])
        val fila = JsonSifec.parseToJsonElement(p.cuerpoTexto!!).jsonObject
        assertEquals(setOf("tipo", "subtipo", "descripcion", "foto_url", "geom"), fila.keys)   // autor, estado, confianza los pone la BD
        assertEquals("atasco", fila["tipo"]!!.jsonPrimitive.content)
        assertEquals("leve", fila["subtipo"]!!.jsonPrimitive.content)
        assertEquals("pista anegada", fila["descripcion"]!!.jsonPrimitive.content)
        assertEquals("null", fila["foto_url"].toString())
        assertEquals("SRID=4326;POINT(-78.51 -7.16)", fila["geom"]!!.jsonPrimitive.content)
    }

    @Test
    fun arma_votar_comentar_foto_y_rpc() {
        val c = comunidad()
        val votar = c.peticionVotar(TOKEN, "r1", -1)
        assertEquals("$URL/rest/v1/voto?on_conflict=report_id%2Cautor", votar.url)
        assertEquals("resolution=merge-duplicates,return=minimal", votar.cabeceras["Prefer"])
        assertEquals("""{"report_id":"r1","valor":-1}""", votar.cuerpoTexto)
        val quitar = c.peticionQuitarVoto(TOKEN, "r1")
        assertEquals("DELETE", quitar.metodo)
        assertEquals("$URL/rest/v1/voto?report_id=eq.r1", quitar.url)

        val comentar = c.peticionComentar(TOKEN, "r1", "lo vi")
        assertEquals("$URL/rest/v1/comentario?select=id%2Creport_id%2Ctexto%2Ccreado_en", comentar.url)
        assertEquals("""{"report_id":"r1","texto":"lo vi"}""", comentar.cuerpoTexto)
        assertEquals("return=representation", comentar.cabeceras["Prefer"])

        val ruta = ComunidadSupabase.rutaFoto(UID, ahoraMs = 1763550000000, aleatorio = "ab12cd")
        assertEquals("$UID/1763550000000-ab12cd.jpg", ruta)
        assertTrue(Regex("^[0-9a-f-]{36}/[A-Za-z0-9_-]{1,80}\\.jpg$").matches(ruta))   // lo que exige report_foto_url_check
        val foto = c.peticionSubirFoto(TOKEN, ruta, byteArrayOf(1, 2, 3))
        assertEquals("$URL/storage/v1/object/reportes/$ruta", foto.url)
        assertEquals("image/jpeg", foto.cabeceras["Content-Type"])
        assertEquals("false", foto.cabeceras["x-upsert"])
        assertEquals("Bearer $TOKEN", foto.cabeceras["Authorization"])
        assertEquals("$URL/storage/v1/object/public/reportes/$ruta", c.urlFotoPublica(ruta))

        val mis = c.peticionMisReportes(TOKEN)
        assertEquals("$URL/rest/v1/rpc/mis_reportes", mis.url)
        assertEquals("POST", mis.metodo)
        assertEquals("GET", c.peticionPerfil(TOKEN).metodo)
        assertEquals("$URL/rest/v1/perfil?select=id%2Cnombre%2Creputacion&limit=1", c.peticionPerfil(TOKEN).url)
        assertTrue(c.peticionMisVotos(TOKEN, listOf("a", "b")).url.contains("report_id=in.%28a%2Cb%29"))
    }

    @Test
    fun crear_reporte_con_transporte_simulado_y_errores_claros() = runTest {
        val fila = """[{"id":"r9","tipo":"inundacion","subtipo":null,"descripcion":"calle anegada","foto_url":null,"likes":0,"dislikes":0,"confianza":0.5,"estado":"sin_confirmar","creado_en":"2026-11-19T15:00:00+00:00","expira_en":"2026-11-20T03:00:00+00:00","lat":-7.16,"lon":-78.51,"autor":"nunca"}]"""
        val t = TransporteFalso(listOf(RespuestaHttp(201, fila)))
        val r = comunidad(t).crearReporte("inundacion", null, "calle anegada", null, -7.16, -78.51)
        assertEquals("r9", r.id)
        assertEquals("sin_confirmar", r.estado)
        assertEquals("Bearer $TOKEN", t.enviadas.single().cabeceras["Authorization"])

        // limite por hora de la BD
        val t2 = TransporteFalso(listOf(RespuestaHttp(400, """{"code":"P0001","message":"límite de 5 por hora alcanzado"}""")))
        try {
            comunidad(t2).crearReporte("inundacion", null, null, null, -7.16, -78.51)
            assertTrue("debia fallar", false)
        } catch (e: ErrorConsulta) {
            assertEquals("Llegaste al límite de 5 por hora. Espera un rato antes de volver a enviar el reporte.", e.message)
        }
        // sin sesion: no se manda nada
        val t3 = TransporteFalso(listOf(RespuestaHttp(200, "[]")))
        try {
            comunidad(t3, token = null).votar("r1", 1)
            assertTrue("debia fallar", false)
        } catch (e: ErrorConsulta) {
            assertEquals(Comunidad.SESION_VENCIDA, e.message)
            assertTrue(t3.enviadas.isEmpty())
        }
        // mis reportes (rpc) y perfil
        val t4 = TransporteFalso(listOf(RespuestaHttp(200, fila), RespuestaHttp(200, """[{"id":"$UID","nombre":"Rosa","reputacion":3,"zona":"0101000020E6100000"}]""")))
        val c4 = comunidad(t4)
        assertEquals(listOf("r9"), c4.misReportes().map { it.id })
        assertEquals(3, c4.perfil()!!.reputacion)
        // una foto demasiado pesada no se manda
        try {
            comunidad(t4).subirFoto(ByteArray(Comunidad.MAX_FOTO_BYTES + 1), UID)
            assertTrue("debia fallar", false)
        } catch (e: ErrorConsulta) {
            assertEquals("La foto pesa demasiado (máximo 3 MB).", e.message)
        }
    }
}
