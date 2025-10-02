import axios from 'axios';
export interface ApiHotel {
  id: number;
  name: string;
}

export interface CrawlerOptions {
  otas: string[];
  startDate: string | null;
  endDate: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

/**
 * クローラーの実行をバックエンドにリクエストする関数
 */
export const runCrawler = async (
  hotel: ApiHotel,
  options: CrawlerOptions
): Promise<string> => {
  const payload = {
    hotel: { id: hotel.id, name: hotel.name },
    options: options,
  };

  try {
    const response = await axios.post(`${API_URL}/crawlers/start/`, payload);
    return response.data.message || 'クローラーの処理を開始しました。';
  } catch (error: any) {
    console.error('クローラーの起動に失敗しました:', error);
    const errorMessage =
      error.response?.data?.error ||
      'サーバーとの通信中にエラーが発生しました。';
    throw new Error(errorMessage);
  }
};

/**
 * レビューデータのエクスポートとダウンロードを処理する関数
 */
export const exportFile = async (
  hotel: ApiHotel,
  options: CrawlerOptions
): Promise<void> => {
  const payload = {
    hotel: { id: hotel.id, name: hotel.name },
    options: options,
  };

  try {
    const response = await axios.post(`${API_URL}/export/`, payload, {
      responseType: 'blob',
    });

    // ファイルダウンロード処理
    const contentDisposition = response.headers['content-disposition'];
    let filename = 'export.xlsx';
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
      if (filenameMatch?.[1]) {
        filename = decodeURIComponent(filenameMatch[1]);
      }
    }

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.parentNode?.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (err: any) {
    console.error('エクスポートに失敗しました:', err);
    // Blob形式のエラーレスポンスをテキストに変換して処理する
    if (err.response?.data instanceof Blob) {
      const errorText = await err.response.data.text();
      try {
        const errorJson = JSON.parse(errorText);
        throw new Error(errorJson.error || '不明なエラーが発生しました。');
      } catch {
        throw new Error('サーバーから予期せぬエラーが返されました。');
      }
    }
    throw new Error('エクスポート処理中にエラーが発生しました。');
  }
};
