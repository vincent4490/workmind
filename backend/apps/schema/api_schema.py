# -*- coding: utf-8 -*-
"""
@File    : api_schema.py
@Time    : 2023/12/14 11:16
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : API鏁版嵁妯℃澘
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class APIBody(BaseModel):
    name: str
    rig_id: int
    times: int
    request: Dict
    desc: Dict
    extract: Optional[List] = []
    check: List = Field([], alias="validate")


class APISchema(BaseModel):
    name: str
    body: APIBody
    url: str
    method: str
    relation: int
    creator_id: int
