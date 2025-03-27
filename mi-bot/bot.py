import discord
import os
import random
from typing import Dict, List
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Crear cliente
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Necesario para enviar mensajes privados
client = discord.Client(intents=intents)

# Estructura para almacenar partidas
partidas: Dict[str, Dict] = {}  # {canal_id: partida_info}
jugadores_por_partida: Dict[str, List[Dict]] = {}  # {canal_id: [jugadores]}

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
    
    if num_jugadores < 5:
        return "❌ Se necesitan al menos 5 jugadores para una partida de Mafia."
    
    partidas[canal_id] = {
        "creador": creador_id,
        "max_jugadores": num_jugadores,
        "estado": "esperando",
        "roles_asignados": False
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
    partida["estado"] = "en_juego"
    
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
    
    return True

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content.lower() == 'hola':
        await message.channel.send('¡Hola! Soy un bot hecho en Python. 🤖')
    
    # Comandos de Mafia
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

# Iniciar el bot
client.run(TOKEN)