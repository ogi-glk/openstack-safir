############################################################
#           SAFIR CLOUD LICENCE KEY GENERATION             #
############################################################

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from datetime import datetime
import re


# Change the following values to generate a licence
# and copy the licence string to safir_cloud_watcher.conf file
destination_address = "SAFIRBULUTTEST"
valid_until = datetime(2028, 1, 1)  # year, month, day
cpu_core_limit = 50000
poc = 0  # 1 if true else 0


# Do not modify the following code

FERNET_KEY = b'9Ovua_Aud3bBzN3Vymd5VKNRBLr4yyM4TAcxSQ9v6n4='
f = Fernet(FERNET_KEY)

licence_txt = "TUBITAK_BILGEM_"

licence_txt += destination_address.ljust(17)[:17]
licence_txt += "_"

licence_txt += valid_until.strftime("%Y%m%d")

licence_txt += str(cpu_core_limit).zfill(5)

licence_txt += str(poc)

key_footer = "_SAFIR_BULUT"

licence_txt += key_footer

print("Licence Text: ", licence_txt)

encrypted_licence_key = f.encrypt(licence_txt.encode())

print("\n\n========= LICENSE BEGIN ======== ")
print(encrypted_licence_key.decode())
print("========== LICENSE END =========\n")


encrypted_notification_counter = f.encrypt("0".encode())

print("\n========= NOTIFICATION COUNTER BEGIN ======== ")
print(encrypted_notification_counter.decode())
print("========== NOTIFICATION COUNTER END =========\n\n")


# VALIDATION

try:
    decrypted_string = f.decrypt(encrypted_licence_key)
except InvalidToken:
    print("Token not valid")
    decrypted_string = ""


print("Licence length:", len(decrypted_string))

print("Decrypted Licence: ", decrypted_string)
destination_address_ = decrypted_string[15:32].decode().strip()
print(destination_address_)

valid_until_str_ = decrypted_string[33:41].decode()
valid_until_ = datetime.strptime(valid_until_str_, '%Y%m%d')
print(valid_until_)

if datetime.now() > valid_until_:
    print("due date exceeded")
else:
    print("date valid")

cpu_core_limit_ = int(decrypted_string[41:46].decode())
print(cpu_core_limit_)

poc_ = int(decrypted_string[46:47].decode())
print(poc_)

try:
    decrypted_notification_counter = f.decrypt(encrypted_notification_counter)
except InvalidToken:
    print("Token not valid")
    decrypted_notification_counter = ""

print(decrypted_notification_counter)


print("\n\nSQL SCRIPT\n")
print("INSERT INTO licence (created_at, deleted, licence_key, notification_address, notification_counter) "
      "VALUES (NOW(), 0, '" + encrypted_licence_key.decode() + "', 'ozkan.esra@tubitak.gov.tr', '" +
      encrypted_notification_counter.decode() + "');")
