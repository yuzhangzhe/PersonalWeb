# -*- coding: utf-8 -*-  # 声明源码编码为 UTF-8，保证中文注释与输出在 Windows 下不乱码
import json  # 标准库：把自测结果序列化为统一返回结构
import re  # 标准库：用正则提取章节标题与证据编号
import sys  # 标准库：失败时以非零退出码告知调用方
from pathlib import Path  # 标准库：按脚本自身位置定位提示词文件，避免依赖当前工作目录

PROMPT_FILE = Path(__file__).with_name("运费对账智能体_开发提示词.md")  # 待校验的提示词文件，与脚本同目录
SECTIONS = [  # 原模板的七个章节标题，一个都不能少
    "## 【项目背景】",  # 业务事件、基线、流程、异常与待办
    "## 【系统定位】",  # 首期范围与 AI 能力边界
    "## 【用户与权限】",  # 六角色权限矩阵
    "## 【技术栈，不许替换】",  # 零新增依赖与禁止引入清单
    "## 【数据红线，硬约束】",  # 只读、脱敏、审计、验收与停止条件
    "## 【代码规范】",  # 用户给出的五条代码规范
    "## 【交付要求】",  # 每阶段四项交付物与阶段划分
]  # 章节清单结束
KEYWORDS = [  # 关键硬约束关键词，缺一即判提示词填写不完整
    "可重现率 100%",  # 验收底线：计费结果可重现
    "未授权扣费为零",  # 验收底线：不得出现未授权扣费
    "两家承运商",  # 试点范围：两家承运商并行试点
    "只读核对",  # 首期安全边界：只读核对与人工交接
    "人工确认",  # 建议进入流程前必须人工确认
    "config.yaml",  # 密钥与模型地址只能落在配置文件
    '"ok": bool',  # 统一返回结构的 ok 字段
    "每行代码必须添加注释",  # 代码规范：每行注释
    "六类审计字段",  # 每次建议留业务编号等六类字段
    "四类",  # 四类资料与四类转人工
    "停止条件",  # 触及即暂停试点的条件
    "零新增依赖",  # 技术栈未指定前的默认执行口径
    "禁止擅自引入",  # 不引入未要求的中间件
    "f00",  # 证据编号起点
    "f55",  # 证据编号终点
]  # 关键词清单结束
ROLES = [  # 六角色，权限矩阵必须逐一覆盖
    "顾明岚",  # 结算经理
    "林亦舟",  # 运单录入员
    "唐映秋",  # 对账专员
    "秦芮",  # 计费系统工程师
    "傅景",  # 合同审计专员
    "叶书",  # 承运商结算代表
]  # 角色清单结束
FORBIDDEN = [  # 未填写的模板占位残留，出现即判失败
    "TODO",  # 常见待办占位
    "待填写",  # 中文待填写占位
    "********",  # 原模板被打码的系统名占位符
    "（此处填空）",  # 显式填空占位
]  # 占位清单结束


def read_prompt(path):
    """读取提示词全文。

    入参：path，pathlib.Path，提示词文件路径。
    出参：二元组 (text, error)，成功时 text 为文件全文字符串、error 为 None。
    失败时的行为：文件不存在或读取异常时返回 ("", 中文错误说明)，不抛异常、不中断进程。
    """
    try:  # 捕获文件缺失与编码异常，统一转成可判定的错误信息
        return path.read_text(encoding="utf-8"), None  # 按 UTF-8 读取全文并正常返回
    except OSError as exc:  # 文件不存在、无权限或解码失败均落入此分支
        return "", "读取提示词文件失败：" + str(exc)  # 返回空文本与中文失败原因


def check_sections(text):
    """校验七个章节标题齐全且没有空段。

    入参：text，str，提示词全文。
    出参：list[str]，校验失败项说明；全部通过时返回空列表。
    失败时的行为：逐项收集缺失标题与空段，不抛异常、不提前返回。
    """
    errors = []  # 累积本函数发现的全部失败项
    for title in SECTIONS:  # 逐个检查模板要求的章节标题
        if title not in text:  # 标题缺失即记为一条失败项
            errors.append("缺少章节：" + title)  # 记录具体缺失的章节名
    empty = re.search(r"## 【[^】]+】\s*\n\s*\n\s*## ", text)  # 匹配「标题后紧跟下一个标题」的空段
    if empty:  # 存在空段说明该章节未填写
        errors.append("存在未填写的空章节：" + empty.group(0).split("\n")[0])  # 记录空章节标题
    return errors  # 返回全部章节相关失败项


def check_keywords(text):
    """校验硬约束关键词、六角色与占位残留。

    入参：text，str，提示词全文。
    出参：list[str]，校验失败项说明；全部通过时返回空列表。
    失败时的行为：逐项收集缺失关键词、缺失角色与残留占位，不抛异常、不提前返回。
    """
    errors = []  # 累积本函数发现的全部失败项
    for word in KEYWORDS:  # 逐个检查硬约束关键词
        if word not in text:  # 关键词缺失即记为一条失败项
            errors.append("缺少硬约束关键词：" + word)  # 记录具体缺失的关键词
    for role in ROLES:  # 逐个检查六角色是否都在权限矩阵中
        if role not in text:  # 角色缺失即记为一条失败项
            errors.append("权限矩阵缺少角色：" + role)  # 记录具体缺失的角色
    for mark in FORBIDDEN:  # 逐个检查模板占位是否残留
        if mark in text:  # 占位残留说明填写未完成
            errors.append("存在未填写占位：" + mark)  # 记录具体残留的占位符
    return errors  # 返回全部关键词相关失败项


def check_evidence(text):
    """校验证据编号覆盖度。

    入参：text，str，提示词全文。
    出参：list[str]，校验失败项说明；覆盖数达标时返回空列表。
    失败时的行为：编号不足 25 个时返回一条失败项，不抛异常。
    """
    found = set(re.findall(r"f\d{2}", text))  # 提取全文中出现的 fNN 形式证据编号并去重
    if len(found) < 25:  # 编号覆盖过少说明事实依据未落到正文
        return ["证据编号覆盖不足：仅 " + str(len(found)) + " 个，要求不少于 25 个"]  # 返回覆盖不足说明
    return []  # 覆盖达标，返回空列表


def build_result(errors, checks, evidence_count):
    """构造对外统一返回结构。

    入参：errors 为失败项列表，checks 为已执行的校验项总数，evidence_count 为命中的证据编号个数。
    出参：dict，形如 {"ok": bool, "data": ..., "error": {"code": str, "msg": str}}。
    失败时的行为：errors 非空时 ok 置 False、error.code 置 PROMPT_INCOMPLETE、msg 拼接全部失败项；不抛异常。
    """
    ok = len(errors) == 0  # 无失败项即判定校验通过
    data = {  # 成功与失败时都给出可核对的统计信息
        "file": str(PROMPT_FILE),  # 被校验的文件路径
        "checks": checks,  # 本次执行的校验项总数
        "evidence_ids": evidence_count,  # 正文中命中的不同证据编号个数
    }  # data 字典结束
    error = {  # 统一错误结构，成功时 code 与 msg 均为空串
        "code": "" if ok else "PROMPT_INCOMPLETE",  # 失败时给出稳定的错误码
        "msg": "" if ok else "；".join(errors),  # 失败时拼接全部失败原因
    }  # error 字典结束
    return {"ok": ok, "data": data, "error": error}  # 返回统一结构


def main():
    """入口：串联读取、三类校验与结果输出。

    入参：无。
    出参：int，进程退出码，通过为 0、失败为 1。
    失败时的行为：打印 ok=False 的统一结构并返回 1，不抛出堆栈。
    """
    sys.stdout.reconfigure(encoding="utf-8")  # 强制 UTF-8 输出，避免 Windows 控制台中文乱码
    text, read_error = read_prompt(PROMPT_FILE)  # 读取提示词全文，失败时拿到中文错误说明
    if read_error:  # 读取失败时无需继续做内容校验
        result = build_result([read_error], 0, 0)  # 直接构造失败结构
        print(json.dumps(result, ensure_ascii=False, indent=2))  # 打印统一返回结构
        return 1  # 以非零退出码告知调用方
    errors = []  # 累积全部校验失败项
    errors += check_sections(text)  # 校验章节齐全与无空段
    errors += check_keywords(text)  # 校验硬约束、角色与占位残留
    errors += check_evidence(text)  # 校验证据编号覆盖度
    checks = len(SECTIONS) + len(KEYWORDS) + len(ROLES) + len(FORBIDDEN) + 2  # 统计已执行的校验项总数
    found = set(re.findall(r"f\d{2}", text))  # 再次提取编号，仅用于结果统计
    result = build_result(errors, checks, len(found))  # 构造统一返回结构
    print(json.dumps(result, ensure_ascii=False, indent=2))  # 打印统一返回结构
    return 0 if result["ok"] else 1  # 通过返回 0，失败返回 1


if __name__ == "__main__":  # 仅作为脚本直接执行时启动，被 import 时不触发
    sys.exit(main())  # 把 main 的返回值作为进程退出码
