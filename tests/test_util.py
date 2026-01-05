from services.util import convert_ft_to_m, convert_m_to_ft


def test_convert_ft_to_m():
    assert convert_ft_to_m(0) == 0.0
    assert convert_ft_to_m(3.28084) == 1.0
    assert convert_ft_to_m(10) == 3.048
    assert convert_ft_to_m(None) is None
    assert convert_ft_to_m(10, ndigits=4) == 3.048


def test_convert_m_to_ft():
    assert convert_m_to_ft(0) == 0.0
    assert convert_m_to_ft(1) == 3.28084
    assert convert_m_to_ft(3.048) == 10.0
    assert convert_m_to_ft(None) is None
    assert convert_m_to_ft(3.048, ndigits=4) == 10.0
