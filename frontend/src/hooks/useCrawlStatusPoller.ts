import { useState, useEffect } from 'react';
import axios, { AxiosError } from 'axios';

type CrawlStatusValue = 'PENDING' | 'SUCCESS' | 'FAILURE' | 'NEVER_RUN';

export interface CrawlStatus {
  id: number;
  ota_name: string;
  last_crawl_status: CrawlStatusValue;
  last_crawled_at: string | null;
  last_crawl_message: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface UseCrawlStatusPollerProps {
  hotelName: string | null;
  interval?: number;
}

interface UseCrawlStatusPollerReturn {
  statusData: CrawlStatus[];
  isLoading: boolean;
  error: AxiosError | null;
}

export function useCrawlStatusPoller({
  hotelName,
  interval = 5000,
}: UseCrawlStatusPollerProps): UseCrawlStatusPollerReturn {
  const [statusData, setStatusData] = useState<CrawlStatus[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AxiosError | null>(null);

  const isPollingStopped =
    statusData.length > 0 &&
    statusData.every(
      (target) =>
        target.last_crawl_status === 'SUCCESS' ||
        target.last_crawl_status === 'FAILURE'
    );

  useEffect(() => {
    if (!hotelName) {
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        const response = await axios.get<CrawlStatus[]>(
          `${API_URL}/crawl-status/${hotelName}/`
        );

        if (isMounted) {
          setStatusData(response.data);
        }
      } catch (err) {
        if (isMounted) {
          if (axios.isAxiosError(err)) {
            setError(err);
          } else {
            setError(new AxiosError('An unexpected error occurred'));
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchData();

    let intervalId: NodeJS.Timeout | null = null;
    if (!isPollingStopped) {
      intervalId = setInterval(fetchData, interval);
    }

    return () => {
      isMounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [hotelName, interval, isPollingStopped]);

  return { statusData, isLoading, error };
}
