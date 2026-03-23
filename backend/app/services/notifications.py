from app.models.player import Player
from app.models.game import Game
from app.services.sms import send_sms
from app.services.push import send_push
from app.config import settings


def notify_player(player: Player, game: Game) -> None:
    """Send confirmation request to a player via SMS and/or push notification."""
    confirm_url = f"{settings.BASE_URL}/api/confirm"
    message = (
        f"Hi {player.first_name}! You are up for game #{game.id}. "
        f"Reply YES, NO, or DEFER within {settings.CONFIRM_TIMEOUT_SECONDS // 60} minutes. "
        f"Or confirm at: {settings.BASE_URL}"
    )

    send_sms(player.phone, message)

    if player.expo_push_token:
        send_push(
            token=player.expo_push_token,
            title="Volleyball Game Ready!",
            body=f"Game #{game.id} is starting. Reply YES, NO, or DEFER.",
            data={"game_id": game.id, "player_id": player.id, "action": "confirm"},
        )
