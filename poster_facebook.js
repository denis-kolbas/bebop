const { uploadReels } = require('facebook-reels-api');

async function postReel() {
  try {
    const videoUrl = 'https://storage.googleapis.com/bebop_data/videos/2025-05-29/stitched/stitched_reel_2025-05-29.mp4';
    const accessToken = process.env.FACEBOOK_ACCESS_TOKEN;
    const description = "Today's Music Discoveries! 🎵 #NewMusic #MusicDiscovery";
    
    console.log('Uploading reel...');
    const result = await uploadReels({
      url: videoUrl,
      access_token: accessToken,
      description: description
    });
    
    console.log('✅ Reel posted successfully!', result);
  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}

postReel();