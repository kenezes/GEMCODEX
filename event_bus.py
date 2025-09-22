import logging

class EventBus:
    """Простая шина событий для слабой связи между компонентами."""
    def __init__(self):
        self.subscribers = {}
        logging.info("EventBus initialized.")

    def subscribe(self, event_type, callback):
        """Подписывает обратный вызов на событие."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
            logging.info(f"Subscribed {getattr(callback, '__name__', 'callback')} to '{event_type}'")

    def unsubscribe(self, event_type, callback):
        """Отписывает обратный вызов от события."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
                logging.info(f"Unsubscribed {getattr(callback, '__name__', 'callback')} from '{event_type}'")
            except ValueError:
                # Подавление ошибки, если обратный вызов уже отписан
                pass

    def emit(self, event_type, *args, **kwargs):
        """
        Публикует событие, уведомляя всех подписчиков.
        (Ранее этот метод назывался 'post').
        """
        if event_type in self.subscribers:
            # Копируем список, чтобы избежать проблем при отписке внутри обработчика
            for callback in self.subscribers[event_type][:]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Error in event handler for '{event_type}': {e}", exc_info=True)

