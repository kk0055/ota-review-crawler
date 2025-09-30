import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

interface TaskData {
  status: 'PENDING' | 'SUCCESS' | 'FAILURE';
  result_message: string | null;
}

/**
 * タスクの状態を定期的にポーリングし、結果をトースト通知で表示するカスタムフック
 * @returns pollTaskStatus - ポーリングを開始するための関数
 */
export const useTaskPoller = () => {
  const pollTaskStatus = (taskId: string) => {
    // setIntervalのIDを保持するための変数
    let intervalId: NodeJS.Timeout;

    const checkStatus = async () => {
      try {
        const response = await axios.get<TaskData>(
          `http://localhost:8000/api/tasks/${taskId}/`
        );
        const { status, result_message } = response.data;

        // タスクが完了（成功 or 失敗）したらポーリングを停止
        if (status === 'SUCCESS' || status === 'FAILURE') {
          clearInterval(intervalId);

          if (status === 'SUCCESS') {
            toast.success(result_message || '処理が正常に完了しました！');
          } else {
            // FAILURE
            toast.error(
              `処理に失敗しました: ${result_message || '詳細不明のエラー'}`
            );
          }
        }
        // statusが 'PENDING' の場合は何もしない（次のポーリングを待つ）
      } catch (error) {
        console.error('Polling error:', error);
        clearInterval(intervalId); // エラーが発生した場合もポーリングを停止
        toast.error('タスクの状態取得中にエラーが発生しました。');
      }
    };
    intervalId = setInterval(checkStatus, 5000);
  };

  return { pollTaskStatus };
};

export default useTaskPoller;
