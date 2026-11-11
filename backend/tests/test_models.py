"""Model phải giữ đúng các ràng buộc của schema SQL."""
import pytest
from sqlalchemy.exc import IntegrityError

import models


def make_user(**over):
    d = dict(student_id="25520001", email="25520001@gm.uit.edu.vn", password_hash="x", full_name="A")
    d.update(over)
    return models.User(**d)


def test_student_id_column_matches_eight_digit_business_rule():
    assert models.User.__table__.c.student_id.type.length == 8


def test_email_domain_check_is_anchored(session_factory):
    with session_factory() as s:
        s.add(make_user(email="25520001@gm.uit.edu.vn.evil.com"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_product_check_constraints(session_factory):
    with session_factory() as s:
        s.add(make_user())
        s.commit()
        for bad in ({"price": -1}, {"condition": "Broken"}, {"status": "Deleted"}):
            fields = dict(seller_id=1, category_id=1, title="t", price=1, condition="Good")
            fields.update(bad)
            s.add(models.Product(**fields))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_updated_at_changes_on_update(session_factory):
    import time

    with session_factory() as s:
        u = make_user()
        s.add(u)
        s.commit()
        first = u.updated_at
        time.sleep(1.1)
        u.full_name = "B"
        s.commit()
        assert u.updated_at > first
