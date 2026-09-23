# Mission Controlの起動

現在の導入・起動手順は [README](../README.md) を参照してください。

- `bash scripts/setup.sh`：初回セットアップ。
- `bash scripts/gouda.sh view`：実機データを待つGUIと標準RVizを起動。
- `bash scripts/gouda.sh observe`：設定済みのLiDAR・IMU受信を追加。
- `bash scripts/gouda.sh doctor`：接続と更新状態を診断。
- `bash scripts/gouda.sh stop`：管理対象だけ停止。

入口は `http://127.0.0.1:8766`。デモの地図や座標は生成しません。
初期位置・ゴール設定は走行用2D地図で行い、標準RViz内の局所点群とは区別します。
観測モードでは車両への走行出力を起動しません。
