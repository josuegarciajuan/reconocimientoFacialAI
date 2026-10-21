import unittest
from unittest.mock import patch

import motor.core.camara_perfil as camara_perfil
from motor.core.camara_perfil import (
    camera_id_from_url,
    fetch_profile,
    latest_jpeg_url,
    profile_fps,
    profile_stream_size,
)


class CamaraPerfilTests(unittest.TestCase):
    def test_detecta_urls_camaraip(self):
        self.assertEqual(
            camera_id_from_url("http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina"),
            "cam-oficina",
        )
        self.assertEqual(
            camera_id_from_url("https://josue.ink/camaraip/latest.jpg?camera=esp32-oficina"),
            "esp32-oficina",
        )

    def test_no_detecta_rtsp_ni_ojos(self):
        self.assertIsNone(camera_id_from_url("rtsp://example.invalid/cam?channel=1"))
        self.assertIsNone(camera_id_from_url("https://josue.ink/ojos/admin/?camera=x"))
        self.assertIsNone(camera_id_from_url(""))
        self.assertIsNone(camera_id_from_url(None))

    def test_fallback_sin_bridge(self):
        self.assertEqual(profile_fps("rtsp://example.invalid/cam", 14), 14)
        self.assertIsNone(profile_stream_size("rtsp://example.invalid/cam"))
        self.assertIsNone(latest_jpeg_url("rtsp://example.invalid/cam"))

    def test_urls_locales(self):
        url = "http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina"
        self.assertEqual(
            latest_jpeg_url(url),
            "http://127.0.0.1:8111/camaraip/latest.jpg?camera=cam-oficina",
        )

    def test_prioriza_fps_medido(self):
        data = {"profile": {"stream": {"fps": 5}}, "measured": {"fps": 2.0}}
        with patch("motor.core.camara_perfil.fetch_profile", return_value=data):
            self.assertEqual(
                profile_fps("http://127.0.0.1:8111/camaraip/stream?camera=x", 0),
                2.0,
            )

    def test_usa_perfil_si_no_hay_medida(self):
        data = {"profile": {"stream": {"fps": 5}}, "measured": {"fps": 0}}
        with patch("motor.core.camara_perfil.fetch_profile", return_value=data):
            self.assertEqual(
                profile_fps("http://127.0.0.1:8111/camaraip/stream?camera=x", 0),
                5.0,
            )

    def test_fallback_a_copia_guardada(self):
        camara_perfil._CACHE.clear()
        url = "http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina"
        with patch("motor.core.camara_perfil.urlopen", side_effect=OSError("sin bridge")):
            data = fetch_profile(url)
        self.assertIsNotNone(data)
        self.assertEqual(data["config_source"], "saved")
        self.assertEqual(data["profile"]["stream"]["rotation"], 180)
        self.assertEqual(data["profile"]["model"], "SiGma Micro USB Web Camera")
        camara_perfil._CACHE.clear()
        with patch("motor.core.camara_perfil.urlopen", side_effect=OSError("sin bridge")):
            self.assertGreaterEqual(profile_fps(url, 14), 1)


if __name__ == "__main__":
    unittest.main()
