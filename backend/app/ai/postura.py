"""Análise de postura (RF de visão computacional).

Cada quadro amostrado do vídeo passa pelo Keypoint R-CNN do torchvision, que devolve 17 pontos do
corpo (padrão COCO), em GPU (CUDA) quando houver e em CPU caso contrário (RNF07). Com os pontos,
calculamos os ângulos de joelho, quadril, cotovelo e a inclinação do tronco, contamos repetições e
geramos alertas simples. São heurísticas de apoio ao instrutor, não um diagnóstico.
"""
import base64
import math
import time
from functools import lru_cache

import cv2
import numpy as np
import torch
from torchvision.models.detection import KeypointRCNN_ResNet50_FPN_Weights, keypointrcnn_resnet50_fpn

from .churn import dispositivo

FPS_ALVO = 6         # quadros analisados por segundo de vídeo
MAX_QUADROS = 60     # teto por vídeo (o tempo de análise cresce com isso)
LADO_MODELO = 480    # menor lado da imagem dentro do modelo: menor = mais rápido
LOTE = 4
MIN_PESSOA = 0.8     # confiança mínima da detecção de pessoa
MIN_PONTO = 0.0      # score mínimo de cada ponto do esqueleto

# índices COCO: 5/6 ombros, 7/8 cotovelos, 9/10 punhos, 11/12 quadris, 13/14 joelhos, 15/16 tornozelos
ANGULOS = {
    "joelho_esq": (11, 13, 15), "joelho_dir": (12, 14, 16),
    "quadril_esq": (5, 11, 13), "quadril_dir": (6, 12, 14),
    "cotovelo_esq": (5, 7, 9), "cotovelo_dir": (6, 8, 10),
}
ESQUELETO = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
             (11, 13), (13, 15), (12, 14), (14, 16)]
ARTICULACOES = ("joelho", "quadril", "cotovelo")


@lru_cache(maxsize=1)
def modelo():
    """Na primeira vez o torchvision baixa os pesos (~230 MB) para o cache do torch."""
    m = keypointrcnn_resnet50_fpn(weights=KeypointRCNN_ResNet50_FPN_Weights.COCO_V1,
                                  min_size=LADO_MODELO, max_size=LADO_MODELO * 2)
    return m.to(dispositivo()).eval()


def _ler_quadros(caminho: str):
    cap = cv2.VideoCapture(caminho)
    if not cap.isOpened():
        raise ValueError("Não foi possível abrir o vídeo. Use MP4, MOV, AVI ou WEBM.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    passo = max(1, round(fps / FPS_ALVO))
    if total:
        passo = max(passo, math.ceil(total / MAX_QUADROS))
    quadros, tempos, i = [], [], 0
    while len(quadros) < MAX_QUADROS and cap.grab():
        if i % passo == 0:
            ok, img = cap.retrieve()
            if ok:
                escala = 960 / max(img.shape[:2])
                if escala < 1:  # vídeos grandes: reduz antes, economiza memória e tempo
                    img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
                quadros.append(img)
                tempos.append(i / fps)
        i += 1
    cap.release()
    if not quadros:
        raise ValueError("O vídeo não tem quadros legíveis.")
    duracao = (total or i) / fps
    return quadros, tempos, fps, duracao


def _detectar(quadros: list) -> list:
    """Para cada quadro: (pontos 17x2, scores 17) da pessoa mais provável, ou None."""
    dev, m = dispositivo(), modelo()
    saida = []
    with torch.no_grad():
        for k in range(0, len(quadros), LOTE):
            lote = [torch.from_numpy(cv2.cvtColor(q, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float().div(255).to(dev)
                    for q in quadros[k:k + LOTE]]
            for r in m(lote):
                if len(r["scores"]) == 0 or float(r["scores"][0]) < MIN_PESSOA:
                    saida.append(None)
                else:
                    saida.append((r["keypoints"][0, :, :2].cpu().numpy(), r["keypoints_scores"][0].cpu().numpy()))
    if dev.type == "cuda":
        torch.cuda.synchronize()
    return saida


def _angulo(a, b, c) -> float:
    v1, v2 = a - b, c - b
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))


def _medidas(det) -> dict:
    """Ângulos de um quadro (None quando os pontos não estão visíveis)."""
    if det is None:
        return {}
    pts, sc = det
    ok = lambda *idx: all(sc[i] > MIN_PONTO for i in idx)
    m = {nome: round(_angulo(pts[a], pts[b], pts[c]), 1) for nome, (a, b, c) in ANGULOS.items() if ok(a, b, c)}
    if ok(5, 6, 11, 12):  # inclinação do tronco em relação à vertical (0° = em pé)
        v = (pts[5] + pts[6]) / 2 - (pts[11] + pts[12]) / 2
        m["tronco"] = round(math.degrees(math.atan2(abs(v[0]), abs(v[1]) + 1e-6)), 1)
    return m


def _media_lados(m: dict, art: str):
    vals = [m[k] for k in (f"{art}_esq", f"{art}_dir") if k in m]
    return round(sum(vals) / len(vals), 1) if vals else None


def _suavizar(serie: list, janela: int = 5) -> list:
    """Filtro de MEDIANA (não média): remove picos de 1-2 quadros do rastreamento (ex.: um quadro onde
    o modelo troca os braços ou perde um ponto) sem arredondar o movimento real. Essencial porque a
    detecção de pose oscila bastante quadro a quadro."""
    h = janela // 2
    saida = []
    for i, v in enumerate(serie):
        viz = sorted(x for x in serie[max(0, i - h):i + h + 1] if x is not None)
        saida.append(viz[len(viz) // 2] if v is not None and viz else None)
    return saida


def _instavel(serie_bruta: list, reps: int) -> bool:
    """True quando o sinal da articulação principal oscila muito mais do que as repetições explicam —
    sinal de rastreamento ruim (ângulo/iluminação/pessoa deitada). Nesse caso não dá para julgar
    assimetria ou consistência de repetições com confiança, então esses alertas são suprimidos.
    Num sinal limpo, variação total ≈ 2·reps·amplitude e inversões de direção ≈ 2·reps."""
    d = [serie_bruta[i + 1] - serie_bruta[i] for i in range(len(serie_bruta) - 1)
         if serie_bruta[i] is not None and serie_bruta[i + 1] is not None]
    vals = [v for v in serie_bruta if v is not None]
    if len(vals) < 4 or not d:
        return True
    amplitude = max(vals) - min(vals)
    variacao_total = sum(abs(x) for x in d)
    inversoes = sum(1 for i in range(len(d) - 1) if d[i] * d[i + 1] < 0)
    base = max(reps, 1)
    return (amplitude > 0 and variacao_total / amplitude > 4 * base) or inversoes > 4 * base


def _repeticoes(serie: list) -> int:
    """Conta ciclos "estendido -> flexionado -> estendido" com histerese, para não contar tremidas."""
    vals = [v for v in serie if v is not None]
    if len(vals) < 4 or max(vals) - min(vals) < 30:
        return 0
    lo, hi = min(vals), max(vals)
    baixo, alto = lo + (hi - lo) * 0.35, hi - (hi - lo) * 0.35
    estado, reps = None, 0
    for v in serie:
        if v is None:
            continue
        if v <= baixo:
            estado = "baixo"
        elif v >= alto:
            if estado == "baixo":
                reps += 1
            estado = "alto"
    return reps


def _segmentos_reps(serie: list) -> list:
    """Divide a série da articulação principal em repetições (ciclo alto→baixo→alto), devolvendo
    (fundo, topo) de cada rep — usado para achar repetições parciais ou desiguais."""
    vals = [v for v in serie if v is not None]
    if len(vals) < 4 or max(vals) - min(vals) < 30:
        return []
    lo, hi = min(vals), max(vals)
    nivel_baixo, nivel_alto = lo + (hi - lo) * 0.35, hi - (hi - lo) * 0.35
    reps, estado, fundo = [], None, None
    for v in serie:
        if v is None:
            continue
        if v <= nivel_baixo:
            estado = "baixo"
            fundo = v if fundo is None else min(fundo, v)
        elif v >= nivel_alto:
            if estado == "baixo" and fundo is not None:
                reps.append((fundo, v))  # fechou uma rep: desceu até o fundo e voltou ao topo
                fundo = None
            estado = "alto"
    return reps


def _principal(nome: str, grupo: str | None, resumo: dict) -> str:
    texto = f"{nome} {grupo or ''}".lower()
    if any(p in texto for p in ("agach", "leg", "perna", "afundo", "stiff", "terra", "glúteo", "gluteo", "panturrilha")):
        return "joelho"
    if any(p in texto for p in ("supino", "flex", "rosca", "tríceps", "triceps", "bíceps", "biceps", "remada",
                                "desenvolvimento", "peito", "costas", "ombro", "braço", "braco", "puxada")):
        return "cotovelo"
    amplitudes = {a: resumo.get(a, {}).get("amplitude", 0) for a in ARTICULACOES}
    return max(amplitudes, key=amplitudes.get)


def _resumo(valores: list) -> dict | None:
    vals = [v for v in valores if v is not None]
    if not vals:
        return None
    return {"min": round(min(vals), 1), "max": round(max(vals), 1), "amplitude": round(max(vals) - min(vals), 1),
            "cobertura": round(len(vals) / len(valores), 2)}


def _alertas(principal: str, resumo: dict, pct_pessoa: float, sinal: list, instavel: bool) -> list:
    alertas = []
    superior = principal == "cotovelo"  # supino, rosca, remada, desenvolvimento… (membro superior)
    if pct_pessoa < 0.5:
        alertas.append(f"Pessoa detectada em só {pct_pessoa:.0%} dos quadros. Filme de lado, com o corpo inteiro "
                       "no enquadramento e boa iluminação.")
    if instavel:
        # rastreamento ruim: não dá para avaliar execução. Avisa e não arrisca falsos positivos.
        alertas.append("Rastreamento instável: a detecção do corpo oscilou muito neste vídeo (provável ângulo, "
                       "enquadramento ou iluminação). Filme de lado, com o corpo inteiro no quadro e boa luz, "
                       "para uma avaliação de execução confiável.")
        return alertas
    p = resumo.get(principal)
    esq, dir_ = resumo.get(f"{principal}_esq"), resumo.get(f"{principal}_dir")
    bons_lados = bool(esq and dir_ and min(esq["cobertura"], dir_["cobertura"]) >= 0.6)

    # não completa a flexão (desce pouco)
    if p and p["amplitude"] >= 30 and p["min"] > 100:
        alertas.append(f"Amplitude curta: o {principal} flexionou só até {p['min']:.0f}°. "
                       "Para a amplitude completa, o esperado é chegar perto de 90° ou menos.")

    # membro superior: não estende os braços no topo do movimento
    if superior and p and p["max"] < 150:
        alertas.append(f"Extensão incompleta no topo: o cotovelo chegou só a {p['max']:.0f}° "
                       "(o ideal é estender perto de 170°, travando o movimento no fim).")

    # assimetria no ponto mais baixo (fundo do movimento)
    if bons_lados and abs(esq["min"] - dir_["min"]) > 15:
        alertas.append(f"Diferença de {abs(esq['min'] - dir_['min']):.0f}° entre os lados no {principal} "
                       "(no ponto mais baixo): confira se a carga está equilibrada.")
    # assimetria na extensão: um lado estende menos que o outro no topo
    if bons_lados and abs(esq["max"] - dir_["max"]) > 15:
        lado = "esquerdo" if esq["max"] < dir_["max"] else "direito"
        alertas.append(f"Assimetria na extensão: o lado {lado} estende {abs(esq['max'] - dir_['max']):.0f}° "
                       "a menos que o outro no topo — um braço “fica para trás”.")

    # repetições parciais ou desiguais entre si
    reps = _segmentos_reps(sinal)
    if len(reps) >= 2:
        fundos = [f for f, _ in reps]
        amplitudes = [t - f for f, t in reps]
        if max(fundos) - min(fundos) > 25:
            alertas.append(f"Repetições desiguais: a profundidade variou {max(fundos) - min(fundos):.0f}° "
                           "entre as repetições — procure manter a mesma amplitude em todas.")
        if amplitudes and min(amplitudes) < 0.6 * max(amplitudes):
            alertas.append("Houve repetição parcial: pelo menos uma teve amplitude bem menor que as outras. "
                           "Faça o movimento completo em todas.")

    # tronco à frente (exercícios de perna)
    tronco = resumo.get("tronco")
    if principal == "joelho" and tronco and tronco["max"] > 50:
        alertas.append(f"Tronco muito inclinado à frente (até {tronco['max']:.0f}°): mantenha o peito aberto "
                       "e o abdômen firme.")
    return alertas


def _imagem(quadro, det, medidas: dict, principal: str) -> str | None:
    """Quadro do ponto mais flexionado com o esqueleto desenhado, em JPEG base64 (vai para o histórico)."""
    if det is None:
        return None
    img = quadro.copy()
    pts, sc = det
    for a, b in ESQUELETO:
        if sc[a] > MIN_PONTO and sc[b] > MIN_PONTO:
            cv2.line(img, tuple(map(int, pts[a])), tuple(map(int, pts[b])), (255, 155, 127), 3, cv2.LINE_AA)
    for i in range(5, 17):
        if sc[i] > MIN_PONTO:
            cv2.circle(img, tuple(map(int, pts[i])), 5, (247, 236, 232), -1, cv2.LINE_AA)
    valor = _media_lados(medidas, principal)
    if valor is not None:
        cv2.putText(img, f"{principal} {valor:.0f} graus", (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (99, 122, 255), 2, cv2.LINE_AA)
    escala = 480 / max(img.shape[:2])
    if escala < 1:
        img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode() if ok else None


def analisar(caminho: str, exercicio: str, grupo: str | None) -> dict:
    quadros, tempos, fps, duracao = _ler_quadros(caminho)
    inicio = time.perf_counter()
    deteccoes = _detectar(quadros)
    tempo_ia = time.perf_counter() - inicio

    medidas = [_medidas(d) for d in deteccoes]
    nomes = list(ANGULOS) + ["tronco"]
    # resumo a partir de séries suavizadas por mediana: min/max deixam de ser picos de 1 quadro
    resumo = {n: r for n in nomes if (r := _resumo(_suavizar([m.get(n) for m in medidas])))}
    for art in ARTICULACOES:
        if r := _resumo(_suavizar([_media_lados(m, art) for m in medidas])):
            resumo[art] = r

    principal = _principal(exercicio, grupo, resumo)
    principal_bruto = [_media_lados(m, principal) for m in medidas]
    sinal = _suavizar(principal_bruto)
    reps = _repeticoes(sinal)
    instavel = _instavel(principal_bruto, reps)  # rastreamento ruim desliga os alertas finos
    validos = [i for i, v in enumerate(sinal) if v is not None]
    pior = min(validos, key=lambda i: sinal[i]) if validos else None
    pct_pessoa = sum(d is not None for d in deteccoes) / len(deteccoes)

    return {
        "fps_original": round(fps, 2),
        "fps_processado": round(len(quadros) / tempo_ia, 2) if tempo_ia else None,
        "duracao_seg": round(duracao, 2),
        "resultado": {
            "dispositivo": str(dispositivo()),
            "modelo": "keypointrcnn_resnet50_fpn (COCO)",
            "quadros_analisados": len(quadros),
            "quadros_com_pessoa": sum(d is not None for d in deteccoes),
            "tempo_ia_seg": round(tempo_ia, 2),
            "articulacao_principal": principal,
            "repeticoes": reps,
            "rastreamento_estavel": not instavel,
            "resumo": resumo,
            "serie": [{"t": round(t, 2), **{a: _media_lados(m, a) for a in ARTICULACOES}, "tronco": m.get("tronco")}
                      for t, m in zip(tempos, medidas)],
            "alertas": _alertas(principal, resumo, pct_pessoa, sinal, instavel),
            "imagem": _imagem(quadros[pior], deteccoes[pior], medidas[pior], principal) if pior is not None else None,
        },
    }
