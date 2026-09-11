from __future__ import annotations


def build_text_prompt(system_prompt: str, source_text: str) -> str:
    cleaned = source_text.strip()
    return (
        f"{system_prompt}\n\n"
        "为供桌面程序渲染，请忽略上面关于纯文本输出格式的要求，严格执行以下格式：\n"
        "1. 将全部英文原文按自然句子切分；不得省略、改写、概括或重复任何原文。\n"
        "2. 每个 source 必须逐字保留对应英文，translation 是准确的简体中文译文。\n"
        "3. 只输出一个合法 JSON 对象，不要使用 Markdown 代码块或添加解释。\n"
        '4. JSON 结构必须为：{"pairs":[{"source":"English sentence.",'
        '"translation":"中文译文。"}]}\n\n'
        f"待翻译文本：\n<<<\n{cleaned}\n>>>"
    )


def build_image_prompt(system_prompt: str) -> str:
    return (
        f"{system_prompt}\n\n"
        "为供桌面程序渲染，请忽略上面关于纯文本输出格式的要求，严格执行以下格式：\n"
        "1. 识别所附截图中的全部可辨认英文，并按自然句子或独立文本行切分；"
        "截图已经裁剪到用户选中的区域。\n"
        "2. 每个 source 必须保留截图中对应的英文原文，不得翻译、改写、概括或省略；"
        "translation 是准确的简体中文译文。\n"
        "3. 按截图从上到下、从左到右的阅读顺序排列句对。\n"
        "4. 只输出一个合法 JSON 对象，不要使用 Markdown 代码块或添加解释。\n"
        '5. JSON 结构必须为：{"pairs":[{"source":"English sentence.",'
        '"translation":"中文译文。"}]}。\n'
        '6. 如果截图中没有可辨认的英文，输出：{"pairs":[]}。'
    )
