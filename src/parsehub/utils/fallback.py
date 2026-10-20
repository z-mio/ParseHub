from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from loguru import logger

from ..errors import FallbackAttempt

T = TypeVar("T")


@dataclass(frozen=True)
class FallbackStage(Generic[T]):  # noqa: UP046
    name: str
    func: Callable[[], Awaitable[T]]
    cookie: bool = False


async def run_fallback(  # noqa: UP047
    stages: tuple[FallbackStage[T], ...] | list[FallbackStage[T]],
    *,
    stop: Callable[[Exception], bool],
    wrap: Callable[[Exception, FallbackStage[T]], Exception],
    exhausted: Callable[[list[FallbackAttempt]], Exception],
    label: str = "",
) -> tuple[T, list[FallbackAttempt]]:
    """依次尝试各层, 返回首个成功的结果和之前失败的记录

    :param stop: 返回 True 则中止回退, 直接抛出该层错误
    :param wrap: 包装各层的原始错误
    :param exhausted: 多层全部失败时构造的错误, 只试了一层则透传该层错误
    :param label: 日志前缀
    """
    attempts: list[FallbackAttempt] = []
    for stage in stages:
        try:
            result = await stage.func()
        except Exception as e:
            logger.opt(exception=e).debug(f"{label} {stage.name} 失败")
            err = wrap(e, stage)
            if stop(e):
                if err is e:
                    raise
                raise err from e
            attempts.append(FallbackAttempt(stage.name, err, stage.cookie))
        else:
            return result, attempts

    if len(attempts) == 1:
        raise attempts[0].error
    raise exhausted(attempts) from attempts[-1].error
