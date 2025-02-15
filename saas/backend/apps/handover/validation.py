# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-权限中心(BlueKing-IAM) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from django.utils.functional import cached_property
from rest_framework import serializers

from backend.apps.group.models import Group
from backend.apps.role.models import Role, RoleUser
from backend.biz.group import GroupBiz, SubjectGroupBean
from backend.biz.policy import PolicyQueryBiz
from backend.biz.system import SystemBiz
from backend.service.constants import SubjectType
from backend.service.models.subject import Subject


class BaseHandoverDataProcessor(ABC):
    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def get_info(self):
        pass


class GroupInfoProcessor(BaseHandoverDataProcessor):
    biz = GroupBiz()

    def __init__(self, handover_from: str, group_ids: List[int]) -> None:
        self.handover_from = handover_from
        self.group_ids = group_ids

    def validate(self):
        # 校验用户是否在属于用户组
        now_ts = int(time.time())
        subject_group_id_set = {g.id for g in self.subject_groups if g.expired_at > now_ts}

        for _id in self.group_ids:
            if _id not in subject_group_id_set:
                raise serializers.ValidationError("用户组: {} 不在当前用户的可交接范围内!".format(_id))

    def get_info(self):
        groups = Group.objects.filter(id__in=self.group_ids)
        group_expired_at = {g.id: g.expired_at for g in self.subject_groups}
        return [{"id": group.id, "name": group.name, "expired_at": group_expired_at[group.id]} for group in groups]

    @cached_property
    def subject_groups(self) -> List[SubjectGroupBean]:
        subject = Subject(type=SubjectType.USER.value, id=self.handover_from)
        # NOTE: 可能会有性能问题, 这里需要查询用户的所有组列表
        return self.biz.list_all_subject_group(subject)


class GustomPolicyProcessor(BaseHandoverDataProcessor):
    biz = PolicyQueryBiz()
    system_biz = SystemBiz()

    def __init__(self, handover_from: str, custom_policies: List[Dict[str, Any]]) -> None:
        self.handover_from = handover_from
        self.custom_policies = custom_policies

    def validate(self):
        """
        1. 查询用户的每个系统的自定义权限
        2. 校验id是否在自定义权限中
        """
        subject = Subject(type=SubjectType.USER.value, id=self.handover_from)
        for system_policy in self.custom_policies:
            policies = self.biz.list_by_subject(system_policy["system_id"], subject)
            subject_policy_id_set = {p.policy_id for p in policies if not p.is_expired()}
            for _id in system_policy["policy_ids"]:
                if _id not in subject_policy_id_set:
                    raise serializers.ValidationError(
                        "自定义权限: {}{} 不在当前用户的可交接范围内!".format(system_policy["system_id"], _id)
                    )

    def get_info(self):
        system_list = self.system_biz.new_system_list()
        infos = []
        for system_policy in self.custom_policies:
            sys = system_list.get(system_policy["system_id"])
            infos.append(
                {
                    "id": system_policy["system_id"],
                    "policy_ids": system_policy["policy_ids"],
                    "name": sys.name if sys else "",
                    "name_en": sys.name_en if sys else "",
                }
            )
        return infos


class RoleInfoProcessor(BaseHandoverDataProcessor):
    def __init__(self, handover_from: str, role_ids: List[int]) -> None:
        self.handover_from = handover_from
        self.role_ids = role_ids

    def validate(self):
        for _id in self.role_ids:
            if not RoleUser.objects.user_role_exists(self.handover_from, _id):
                raise serializers.ValidationError("角色: {} 不在当前用户的可交接范围内!".format(_id))

    def get_info(self):
        roles = Role.objects.filter(id__in=self.role_ids)
        return [{"id": role.id, "type": role.type, "name": role.name, "name_en": role.name_en} for role in roles]
