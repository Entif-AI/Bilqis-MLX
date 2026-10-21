"""Independent truth-table oracle for scoped finite event observations."""

VERSION = 'bilqis.issue349.event-frame-oracle/v1'


def independent_answer(record):
    if (not isinstance(record, dict) or record.get('task') != 'bilqis.finite-event-frame/v1'
            or set(record) != {'task', 'events', 'capability', 'query'}):
        raise ValueError('EVENT_FRAME_INVALID_RECORD')
    events = record['events']
    if (not isinstance(events, list) or not 1 <= len(events) <= 4 or
            any(not isinstance(e, list) or len(e) != 3 or
                e[0] not in ('E0','E1','E2','E3') or
                type(e[1]) is not bool or type(e[2]) is not bool for e in events) or
            len({e[0] for e in events}) != len(events)):
        raise ValueError('EVENT_FRAME_INVALID_EVENTS')
    selected = [e for e in events if e[0] == record['query']]
    if len(selected) != 1:
        raise ValueError('EVENT_FRAME_UNDECLARED_QUERY')
    tables = {'D.EVENT_OCCURRENCE': (False, True, False, True),
              'D.COMMENCEMENT': (False, True, False, False),
              'D.TERMINATION': (False, False, True, False)}
    table = tables.get(record['capability'])
    if table is None:
        raise ValueError('EVENT_FRAME_UNKNOWN_CAPABILITY')
    _, before, after = selected[0]
    return 'TRUE' if table[2*int(before)+int(after)] else 'FALSE'
