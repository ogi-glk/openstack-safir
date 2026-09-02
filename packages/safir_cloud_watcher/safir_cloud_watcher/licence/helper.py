# -*- coding: utf-8 -*-
# Copyright 2024 TUBITAK B3LAB
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken


LOTS_OF_RANDOM_STRING = ['EnN8', 'av83', '9Ovu', 'JuhN', 'dg6u',
                         'C7xI', 'NIaE', 'K0qN', 'rk8a', '451b',
                         'BCrm', 'FXoM', 'p0ZN', 'CBVA', '3yNt',
                         'R8AP', '1c5o', 'a_Au', 'u2Ig', 'k95S',
                         'ilBc', 'gkc1', 'd3bB', 'vnbR', 'zN3V',
                         'nAh2', 'Fssm', 'G2YK', 'ymd5', 'OYQN',
                         '5OVh', 'Eu8i', 'VKNR', 'H735', 'FviE',
                         'BLr4', 'MvcW', 'yyM4', '4eJW', 'TAcx',
                         'TwLI', '03rW', 'SQ9v', 'IKJI', 'u28t',
                         'Me7Q', 'oUaG', 'gLY8', '4Pft', '6n4=']


class Helper:
    def __init__(self):
        k = (LOTS_OF_RANDOM_STRING[2] + LOTS_OF_RANDOM_STRING[17] + LOTS_OF_RANDOM_STRING[22] +
             LOTS_OF_RANDOM_STRING[24] + LOTS_OF_RANDOM_STRING[28] + LOTS_OF_RANDOM_STRING[32] +
             LOTS_OF_RANDOM_STRING[35] + LOTS_OF_RANDOM_STRING[37] + LOTS_OF_RANDOM_STRING[39] +
             LOTS_OF_RANDOM_STRING[42] + LOTS_OF_RANDOM_STRING[49])
        self.fernet = Fernet(k)

    def encrypt(self, data):
        try:
            encrypted_str = self.fernet.encrypt(str(data).encode())
        except InvalidToken:
            encrypted_str = ""
        return encrypted_str

    def decrypt(self, encrypted_data):
        try:
            data = self.fernet.decrypt(encrypted_data.encode()).decode()
        except InvalidToken:
            data = ""
        return data
