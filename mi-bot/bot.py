import discord
import os
import random
from typing import Dict, List, Optional
from dotenv import load_dotenv
from enum import Enum, auto 

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True  # Para leer mensajes
intents.messages = True        # Necesario para DMs
intents.dm_messages = True     # Específico para mensajes directos
intents.members = True         # Para ver información de usuarios

client = discord.Client(intents=intents)

# Estructura para almacenar partidas
partidas: Dict[str, Dict] = {}  # {canal_id: partida_info}
jugadores_por_partida: Dict[str, List[Dict]] = {}  # {canal_id: [jugadores]}


class FaseJuego(Enum):
    ESPERANDO = auto()
    NOCHE = auto()
    DIA = auto()
    VOTACION = auto()

# Roles disponibles
ROLES = {
    "Mafioso": {
        "descripcion": "Perteneces a la mafia. De noche, eliminan a un jugador.",
        "maximo": 1  # Por cada 4-5 jugadores se añade otro mafioso
    },
    "Ciudadano": {
        "descripcion": "Eres un ciudadano inocente. Debes encontrar a los mafiosos.",
        "maximo": None  # El resto de jugadores
    },
    "Doctor": {
        "descripcion": "Puedes salvar a un jugador cada noche.",
        "maximo": 1
    },
    "Detective": {
        "descripcion": "Puedes investigar a un jugador cada noche para saber su rol.",
        "maximo": 1
    }
}

async def crear_partida(canal_id: str, creador_id: str, num_jugadores: int):
    """Crea una nueva partida de mafia"""
    if canal_id in partidas:
        return "⚠️ Ya hay una partida en curso en este canal."
    
    if num_jugadores < 4:
        return "❌ Se necesitan al menos 5 jugadores para una partida de Mafia."
    
    partidas[canal_id] = {
        "creador": creador_id,
        "max_jugadores": num_jugadores,
        "estado": "esperando",
        "roles_asignados": False
    }

    partidas[canal_id] = {
        "creador": creador_id,
        "max_jugadores": num_jugadores,  # Asegúrate que esto es un número, no un tipo
        "estado": FaseJuego.ESPERANDO,
        "roles_asignados": False,
        "victima_noche": None,
        "votos_matar": {}
    }
    
    jugadores_por_partida[canal_id] = [{
        "id": creador_id,
        "nombre": f"<@{creador_id}>",
        "rol": None,
        "vivo": True
    }]
    
    return f"🎮 Se ha creado una partida de Mafia para {num_jugadores} jugadores. Usa `!mafia unirme` para participar."

async def unirse_a_partida(canal_id: str, jugador_id: str, jugador_nombre: str):
    """Permite a un jugador unirse a una partida existente"""
    if canal_id not in partidas:
        return "⚠️ No hay partidas activas en este canal. Usa `!mafia crear <número>` para empezar una."
    
    partida = partidas[canal_id]
    
    # Verificar si el jugador ya está en la partida
    for jugador in jugadores_por_partida[canal_id]:
        if jugador["id"] == jugador_id:
            return "⚠️ Ya estás en esta partida."
    
    # Verificar si hay espacio
    if len(jugadores_por_partida[canal_id]) >= partida["max_jugadores"]:
        return "❌ La partida ya está llena."
    
    # Añadir jugador
    jugadores_por_partida[canal_id].append({
        "id": jugador_id,
        "nombre": jugador_nombre,
        "rol": None,
        "vivo": True
    })
    
    # Verificar si se alcanzó el número máximo de jugadores
    jugadores_actuales = len(jugadores_por_partida[canal_id])
    if jugadores_actuales == partida["max_jugadores"]:
        # Asignar roles automáticamente cuando se llena la partida
        await asignar_roles(canal_id)
        return f"✅ {jugador_nombre} se ha unido. ¡Partida completa! Los roles han sido asignados."
    
    return f"✅ {jugador_nombre} se ha unido. Jugadores actuales: {jugadores_actuales}/{partida['max_jugadores']}"

async def asignar_roles(canal_id: str):
    """Asigna roles aleatorios a los jugadores"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    jugadores = jugadores_por_partida[canal_id]
    
    # Calcular número de mafiosos (1 por cada 4 jugadores)
    num_mafiosos = max(1, len(jugadores) // 4)
    
    # Preparar lista de roles a asignar
    roles_a_asignar = []
    
    # Añadir mafiosos
    roles_a_asignar.extend(["Mafioso"] * num_mafiosos)
    
    # Añadir roles especiales (doctor y detective)
    roles_a_asignar.append("Doctor")
    roles_a_asignar.append("Detective")
    
    # El resto son ciudadanos
    roles_a_asignar.extend(["Ciudadano"] * (len(jugadores) - len(roles_a_asignar)))
    
    # Mezclar roles
    random.shuffle(roles_a_asignar)
    
    # Asignar roles a jugadores
    for i, jugador in enumerate(jugadores):
        jugador["rol"] = roles_a_asignar[i]
    
    partida["roles_asignados"] = True
    partida["estado"] = FaseJuego.NOCHE  # Corregir typo en "estado"


    # Enviar mensajes privados con los roles
    for jugador in jugadores:
        rol_info = ROLES[jugador["rol"]]
        mensaje_rol = f"🔮 **Tu rol en la partida de Mafia es: {jugador['rol']}**\n\n"
        mensaje_rol += f"{rol_info['descripcion']}\n\n"
        
        if jugador["rol"] == "Mafioso":
            # Encontrar compañeros mafiosos
            compañeros = [j["nombre"] for j in jugadores if j["rol"] == "Mafioso" and j["id"] != jugador["id"]]
            if compañeros:
                mensaje_rol += f"👥 Tus compañeros mafiosos son: {', '.join(compañeros)}"
        
        # Obtener el objeto User para enviar DM
        user = await client.fetch_user(int(jugador["id"]))
        await user.send(mensaje_rol)

     # Notificar en el canal
    canal = client.get_channel(int(canal_id))
    await canal.send("🎭 **¡Todos los roles han sido asignados!**\n"
                   "La primera noche comienza ahora. Los jugadores especiales recibirán instrucciones por mensaje privado.")
    
    await iniciar_noche(canal_id)

    return True

async def iniciar_noche(canal_id: str):
    """Inicia la fase nocturna de la partida"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    partida["estado"] = FaseJuego.NOCHE
    partida["victima_noche"] = None
    partida["votos_matar"] = {}
    
    # Notificar a todos los jugadores
    canal = client.get_channel(int(canal_id))
    await canal.send("🌙 **Anochece en el pueblo... Todos a dormir!**\n"
                    "Los mafiosos deben decidir a quién eliminar esta noche.")
    
    # Enviar instrucciones específicas por roles
    jugadores = jugadores_por_partida[canal_id]
    for jugador in jugadores:
        if not jugador["vivo"]:
            continue
            
        user = await client.fetch_user(int(jugador["id"]))
        
        if jugador["rol"] == "Mafioso":
            # Lista de jugadores vivos (excepto mafiosos)
            posibles_victimas = [
                j["nombre"] for j in jugadores 
                if j["vivo"] and j["rol"] != "Mafioso"
            ]
            
            await user.send(
                f"🌑 **Es de noche, Mafioso**\n"
                f"Jugadores disponibles para eliminar: {', '.join(posibles_victimas)}\n"
                f"Usa el comando `!matar @jugador` para votar por eliminar a alguien."
            )
        elif jugador["rol"] == "Doctor":
            # Lista de todos los jugadores vivos
            posibles_protegidos = [j["nombre"] for j in jugadores if j["vivo"]]
            
            await user.send(
                f"🏥 **Es de noche, Doctor**\n"
                f"Puedes proteger a un jugador esta noche: {', '.join(posibles_protegidos)}\n"
                f"Usa el comando `!proteger @jugador` para salvar a alguien."
            )
        elif jugador["rol"] == "Detective":
            # Lista de todos los jugadores vivos (excepto sí mismo)
            posibles_investigados = [
                j["nombre"] for j in jugadores 
                if j["vivo"] and j["id"] != jugador["id"]
            ]
            
            await user.send(
                f"🔍 **Es de noche, Detective**\n"
                f"Puedes investigar a un jugador: {', '.join(posibles_investigados)}\n"
                f"Usa el comando `!investigar @jugador` para descubrir su rol."
            )
    
    return True

def procesar_nombre_jugador(input_str: str, jugadores: List[Dict]) -> Optional[Dict]:
    """Convierte '@Bianca' o 'Bianca' al jugador correspondiente"""
    input_str = input_str.strip()
    
    # Caso 1: Es una mención (@Bianca o <@ID>)
    if input_str.startswith('@'):
        nombre_buscado = input_str[1:].lower()
        for j in jugadores:
            if j["nombre"].lower().startswith(nombre_buscado):
                return j
    elif input_str.startswith('<@') and input_str.endswith('>'):
        id_buscado = input_str[2:-1].replace('!', '')
        return next((j for j in jugadores if j["id"] == id_buscado), None)
    
    # Caso 2: Es un nombre plano (Bianca)
    input_lower = input_str.lower()
    for j in jugadores:
        if input_lower in j["nombre"].lower():
            return j
    
    return None

async def procesar_voto_matar(mafioso_id: str, nombre_victima: str, canal_id: str):
    """Procesa el voto de un mafioso para eliminar a un jugador por NOMBRE (no mención)"""
    print(f"[DEBUG] Procesando voto para matar a '{nombre_victima}'")
    
    if canal_id not in partidas:
        print("[DEBUG] No hay partida activa en este canal")
        return False
    
    partida = partidas[canal_id]
    
    # Verificar que sea de noche
    if partida["estado"] != FaseJuego.NOCHE:
        print(f"[DEBUG] No es noche (estado actual: {partida['estado']})")
        return False
    
    jugadores = jugadores_por_partida[canal_id]
    
    # 1. Verificar que el votante es mafioso vivo
    mafioso = next((j for j in jugadores if j["id"] == mafioso_id and j["rol"] == "Mafioso" and j["vivo"]), None)
    if not mafioso:
        print(f"[DEBUG] El jugador {mafioso_id} no es mafioso vivo")
        return False
    
    # Buscar víctima (soporta ambos formatos)
    victima = procesar_nombre_jugador(nombre_victima, jugadores)  # Cambiado de input_victima a nombre_victima
    
    if not victima:
        print(f"[DEBUG] No se encontró jugador válido con nombre: {nombre_victima}")
        print(f"[DEBUG] Jugadores disponibles: {[j['nombre'] for j in jugadores if j['vivo'] and j['rol'] != 'Mafioso']}")
        return False
    
    if not victima["vivo"] or victima["rol"] == "Mafioso":
        print(f"[DEBUG] Víctima no válida. Input: '{nombre_victima}'")
        print(f"Jugadores válidos: {[j['nombre'] for j in jugadores if j['vivo'] and j['rol'] != 'Mafioso']}")
        return False
    
    # Registrar voto
    partida["votos_matar"][mafioso_id] = victima["id"]
    print(f"[DEBUG] Voto registrado: {mafioso_id} -> {victima['nombre']} ({victima['id']})")
    
    
    # Notificar al mafioso
    try:
        user = await client.fetch_user(int(mafioso_id))
        await user.send(f"✅ Has votado por eliminar a {victima['nombre']}.")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar DM: {e}")
    
    # Verificar si todos los mafiosos han votado
    mafiosos_vivos = [j for j in jugadores if j["rol"] == "Mafioso" and j["vivo"]]
    if len(partida["votos_matar"]) == len(mafiosos_vivos):
        print("[DEBUG] Todos los mafiosos han votado")
        # Decidir víctima por mayoría
        victima_id = max(
            set(partida["votos_matar"].values()), 
            key=list(partida["votos_matar"].values()).count
        )
        victima = next(j for j in jugadores if j["id"] == victima_id)
        partida["victima_noche"] = victima_id
        
        # Notificar a los mafiosos
        for m in mafiosos_vivos:
            try:
                user = await client.fetch_user(int(m["id"]))
                await user.send(f"☠️ Decisión final: Eliminar a {victima['nombre']}")
            except:
                continue
    
    return True

async def finalizar_noche(canal_id: str):
    """Finaliza la fase nocturna y procesa las acciones"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    
    # Verificar que sea de noche
    if partida["estado"] != FaseJuego.NOCHE:
        return False
    
    # Procesar la víctima (si hay)
    mensaje_amanecer = "☀️ **Amanece en el pueblo...**\n"
    jugadores = jugadores_por_partida[canal_id]
    
    if partida["victima_noche"]:
        victima = next(j for j in jugadores if j["id"] == partida["victima_noche"])
        victima["vivo"] = False
        mensaje_amanecer += f"🔪 {victima['nombre']} ha sido encontrado/a muerto/a esta mañana.\n"
    else:
        mensaje_amanecer += "¡Todos han sobrevivido la noche!\n"
    
    # Cambiar a fase diurna
    partida["estado"] = FaseJuego.DIA
    canal = client.get_channel(int(canal_id))
    await canal.send(mensaje_amanecer)
    
    return True

async def iniciar_votacion(canal_id: str):
    """Inicia la fase de votación diurna"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    partida["estado"] = FaseJuego.VOTACION
    partida["votos_lynch"] = {}  # {jugador_id: jugador_votado}
    
    # Obtener lista de jugadores vivos
    jugadores = jugadores_por_partida[canal_id]
    vivos = [j for j in jugadores if j["vivo"]]
    
    # Notificar a todos los jugadores
    canal = client.get_channel(int(canal_id))
    await canal.send(
        "🗳️ **Comienza la votación diurna!**\n"
        f"Jugadores vivos: {', '.join(j['nombre'] for j in vivos)}\n"
        "Usa `!votar @jugador` para votar por linchar a alguien."
    )
    
    return True

async def finalizar_votacion(canal_id: str):
    """Finaliza la votación y procesa el resultado"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    
    # Verificar que sea fase de votación
    if partida["estado"] != FaseJuego.VOTACION:
        return False
    
    jugadores = jugadores_por_partida[canal_id]
    vivos = [j for j in jugadores if j["vivo"]]
    
    # Determinar el jugador más votado
    votos = list(partida["votos_lynch"].values())
    if votos:
        victima_id = max(set(votos), key=votos.count)
        victima = next(j for j in jugadores if j["id"] == victima_id)
        victima["vivo"] = False
        
        # Notificar al canal
        canal = client.get_channel(int(canal_id))
        await canal.send(f"⚖️ {victima['nombre']} ha sido linchado por el pueblo!")
        
        # Verificar si el juego ha terminado
        if await verificar_fin_juego(canal_id):
            return True
    else:
        await canal.send("🤷 Nadie recibió votos hoy. El pueblo no ha decidido linchar a nadie.")
    
    return True

async def procesar_voto_lynch(jugador_id: str, votado_nombre: str, canal_id: str):
    """Procesa el voto de un jugador para linchar a otro"""
    if canal_id not in partidas:
        return False
    
    partida = partidas[canal_id]
    
    # Verificar que sea fase de votación
    if partida["estado"] != FaseJuego.VOTACION:
        return False
    
    jugadores = jugadores_por_partida[canal_id]
    
    # Verificar que el votante está vivo
    votante = next((j for j in jugadores if j["id"] == jugador_id and j["vivo"]), None)
    if not votante:
        return False
    
    # Verificar que el votado existe y está vivo
    votado = next((j for j in jugadores if j["nombre"] == votado_nombre and j["vivo"]), None)
    if not votado or votado["id"] == jugador_id:
        return False
    
    # Registrar voto
    partida["votos_lynch"][jugador_id] = votado["id"]
    
    # Notificar al votante
    user = await client.fetch_user(int(jugador_id))
    await user.send(f"✅ Has votado por linchar a {votado_nombre}.")
    
    return True

async def verificar_fin_juego(canal_id: str):
    """Verifica si el juego ha terminado (mafia o ciudadanos ganan)"""
    if canal_id not in partidas:
        return False
    
    jugadores = jugadores_por_partida[canal_id]
    vivos = [j for j in jugadores if j["vivo"]]
    mafiosos_vivos = [j for j in vivos if j["rol"] == "Mafioso"]
    ciudadanos_vivos = [j for j in vivos if j["rol"] != "Mafioso"]
    
    canal = client.get_channel(int(canal_id))
    
    # Mafia gana si igualan o superan en número a los ciudadanos
    if len(mafiosos_vivos) >= len(ciudadanos_vivos):
        await canal.send(
            "🎭 **¡La Mafia ha ganado!**\n"
            f"Mafiosos restantes: {', '.join(m['nombre'] for m in mafiosos_vivos)}\n"
            "El pueblo ha sido dominado por la mafia."
        )
        await terminar_partida(canal_id)
        return True
    
    # Ciudadanos ganan si eliminan a todos los mafiosos
    if not mafiosos_vivos:
        await canal.send(
            "🏡 **¡Los Ciudadanos han ganado!**\n"
            "Todos los mafiosos han sido eliminados.\n"
            "La paz ha vuelto al pueblo."
        )
        await terminar_partida(canal_id)
        return True
    
    return False

async def terminar_partida(canal_id: str):
    """Finaliza la partida y limpia los datos"""
    if canal_id not in partidas:
        return
    
    # Mostrar todos los roles
    jugadores = jugadores_por_partida[canal_id]
    mensaje = "🔍 **Roles de todos los jugadores:**\n"
    for jugador in jugadores:
        mensaje += f"- {jugador['nombre']}: {jugador['rol']}\n"
    
    canal = client.get_channel(int(canal_id))
    await canal.send(mensaje)
    
    # Limpiar datos de la partida
    del partidas[canal_id]
    del jugadores_por_partida[canal_id]

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    print('✅ Bot conectado - Debug inicial funcionando')  # <-- Añade esto

@client.event
async def on_message(message):

    # Debug para todos los mensajes
    print(f"\n📨 Mensaje recibido - Tipo: {'DM' if isinstance(message.channel, discord.DMChannel) else 'Server'}")
    print(f"Contenido: {repr(message.content)}")
    print(f"Autor: {message.author} (ID: {message.author.id})")
    print(f"Canal: {message.channel} (ID: {message.channel.id})")

    if isinstance(message.channel, discord.DMChannel):
        print("🔒 Este es un mensaje directo (DM)")
        # Debug adicional para DMs
        print(f"Bot puede ver DM: {message.channel.me}")  # Debería mostrar info del bot

    if message.author == client.user:
        return
    
    # Comando básico de prueba
    if message.content.lower() == 'hola':
        await message.channel.send('¡Hola! Soy un bot de Mafia. 🤖')
    
    # Comandos de Mafia (!mafia crear/unirme)
    if message.content.startswith('!mafia'):
        comando = message.content.split()
        
        if len(comando) < 2:
            await message.channel.send("❌ Comando inválido. Usa `!mafia crear <jugadores>` o `!mafia unirme`")
            return
        
        if comando[1].lower() == "crear":
            if len(comando) < 3:
                await message.channel.send("❌ Debes especificar el número de jugadores. Ejemplo: `!mafia crear 6`")
                return
            
            try:
                num_jugadores = int(comando[2])
                respuesta = await crear_partida(str(message.channel.id), str(message.author.id), num_jugadores)
                await message.channel.send(respuesta)
            except ValueError:
                await message.channel.send("❌ El número de jugadores debe ser un valor numérico.")
        
        elif comando[1].lower() == "unirme":
            respuesta = await unirse_a_partida(
                str(message.channel.id),
                str(message.author.id),
                message.author.display_name
            )
            await message.channel.send(respuesta)
        
        else:
            await message.channel.send("❌ Comando no reconocido. Usa `!mafia crear <jugadores>` o `!mafia unirme`")

    # Comandos durante el juego (DMs y canal)
    canal_id = str(message.channel.id)
    if canal_id in partidas and partidas[canal_id]["estado"] != FaseJuego.ESPERANDO:
        partida = partidas[canal_id]
        
        # Comandos PRIVADOS (DMs)
        if isinstance(message.channel, discord.DMChannel):
            print(f'[DM] De {message.author}: {message.content}')
            jugadores = jugadores_por_partida[canal_id]
            jugador = next((j for j in jugadores if j["id"] == str(message.author.id)), None)
            
            if not jugador:
                await message.channel.send("⚠️ No estás en una partida activa.")
                return
                
            if not jugador["vivo"]:
                await message.channel.send("💀 Ya has sido eliminado de la partida.")
                return
            
            # Comandos de noche
            if partida["estado"] == FaseJuego.NOCHE:
                if message.content.startswith('!matar') and jugador["rol"] == "Mafioso":
                    input_victima = message.content[len('!matar'):].strip()
                    
                    if not input_victima:
                        await message.channel.send("❌ Usa: `!matar @jugador` o `!matar Nombre`")
                        return
                    
                    if await procesar_voto_matar(
                        mafioso_id=str(message.author.id), 
                        nombre_victima=input_victima,  # Nombre del parámetro corregido
                        canal_id=canal_id
                    ):
                        await message.channel.send(f"✅ Voto registrado contra {input_victima}")
                    else:
                        await message.channel.send("❌ No puedes matar a ese jugador. Razones:")
                        await message.channel.send("- No existe/no está vivo")
                        await message.channel.send("- Es otro mafioso")
                        await message.channel.send("- Comando mal formado")
                    
                elif message.content.startswith('!proteger') and jugador["rol"] == "Doctor":
                    protegido = ' '.join(message.content.split()[1:])
                    # Implementación real de protección
                    await message.channel.send(f"🛡️ Has protegido a {protegido} (acción registrada)")
                    return
                    
                elif message.content.startswith('!investigar') and jugador["rol"] == "Detective":
                    investigado = ' '.join(message.content.split()[1:])
                    # Implementación real de investigación
                    await message.channel.send(f"🔍 Has investigado a {investigado} (acción registrada)")
                    return
            
            # Comandos de votación diurna
            elif partida["estado"] == FaseJuego.VOTACION:
                if message.content.startswith('!votar'):
                    votado = ' '.join(message.content.split()[1:])
                    if await procesar_voto_lynch(str(message.author.id), votado, canal_id):
                        await message.channel.send(f"✅ Voto para linchar a {votado} registrado.")
                    else:
                        await message.channel.send("❌ Voto no válido.")
                    return
        
        # Comandos PÚBLICOS (solo para moderadores)
        if message.content.startswith('!siguiente') and message.author.guild_permissions.administrator:
            if partida["estado"] == FaseJuego.NOCHE:
                await finalizar_noche(canal_id)
                await message.channel.send("🌅 La noche ha terminado. ¡Es de día!")
            elif partida["estado"] == FaseJuego.DIA:
                await iniciar_votacion(canal_id)
            elif partida["estado"] == FaseJuego.VOTACION:
                await finalizar_votacion(canal_id)
                await iniciar_noche(canal_id)
# Iniciar el bot
client.run(TOKEN)