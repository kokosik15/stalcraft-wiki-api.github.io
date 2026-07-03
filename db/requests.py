from db.models import async_session
from db.models import User, Category, Nested_category, Item, Cart, CartItem
from sqlalchemy import select, update, delete, desc, and_

# ========== ПОЛЬЗОВАТЕЛИ ==========
async def set_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            user = User(tg_id=tg_id)
            session.add(user)
            await session.commit()
        return user