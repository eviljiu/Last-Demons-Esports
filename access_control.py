"""Organisation authorization rules. All inputs must come from the server DB."""
import hashlib
import re

OWNER_ID = '乂Jiuシ#1990079'
STAFF_ROLES = frozenset(('FOUNDER', 'CO-FOUNDER', 'AMMINISTRATORE'))
SENIOR_ROLES = frozenset(('FOUNDER', 'CO-FOUNDER'))
ORDINARY_ROLES = ('Player', 'Coach', 'Manager')
ALL_ROLES = ORDINARY_ROLES + ('FOUNDER', 'CO-FOUNDER', 'AMMINISTRATORE')


def canonical_role(value):
    key = re.sub(r'[\s_-]+', '', str(value or '')).upper()
    return {'FOUNDER': 'FOUNDER', 'COFOUNDER': 'CO-FOUNDER',
            'AMMINISTRATORE': 'AMMINISTRATORE', 'PLAYER': 'Player',
            'COACH': 'Coach', 'MANAGER': 'Manager'}.get(key, '')


def approved(player):
    return bool(player and player[4] == 'Approved')


def is_staff(player):
    return approved(player) and canonical_role(player[9]) in STAFF_ROLES


def is_owner(player):
    return approved(player) and player[1] == OWNER_ID


def can_manage_reserved_roles(player):
    return approved(player) and (is_owner(player) or canonical_role(player[9]) in SENIOR_ROLES)


def allowed_roles(actor, target):
    if not target or not (is_staff(actor) or is_owner(actor)):
        return ()
    if can_manage_reserved_roles(actor):
        return ALL_ROLES
    # Admin cannot promote, demote or edit another reserved account, including self.
    if target[1] == OWNER_ID or canonical_role(target[9]) in STAFF_ROLES:
        return ()
    return ORDINARY_ROLES


def can_control_account(actor, target, deleting=False):
    if not is_staff(actor) or not target:
        return False
    if deleting and (target[1] == OWNER_ID or target[0] == actor[0]):
        return False
    reserved = target[1] == OWNER_ID or canonical_role(target[9]) in STAFF_ROLES
    return not reserved or can_manage_reserved_roles(actor)


def auth_stamp(player):
    return hashlib.sha256((str(player[0]) + ':' + str(player[6] or '')).encode()).hexdigest()


def session_matches(player, player_id, stamp):
    return approved(player) and player[1] == player_id and bool(stamp) and auth_stamp(player) == stamp
