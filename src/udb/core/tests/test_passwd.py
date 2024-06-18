# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2022 IKUS Software inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
Created on Apr. 10, 2020

@author: Patrik Dufresne
'''

import unittest

from udb.core.passwd import check_password, hash_password


class Test(unittest.TestCase):
    def test_check_password(self):
        self.assertTrue(hash_password('admin12').startswith('$argon2'))
        self.assertTrue(
            check_password('admin123', '$argon2id$v=19$m=102400,t=2,p=8$/mDhOg8wyZeMTUjcbIC7mg$3pxRSfYgUXmKEKNtasP1Og')
        )
        self.assertTrue(check_password('admin123', '{SSHA}/LAr7zGT/Rv/CEsbrEndyh27h+4fLb9h'))
        self.assertFalse(check_password('admin12', '{SSHA}/LAr7zGT/Rv/CEsbrEndyh27h+4fLb9h'))
        self.assertTrue(check_password('admin12', hash_password('admin12')))
        self.assertTrue(check_password('admin123', hash_password('admin123')))
