class RequestTimeoutException(Exception):
    def __init__(self, message="更新呼啦圈数据时连接失败。"):
        self.message = message
        super().__init__(self.message)