import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3"
import { getSignedUrl } from "@aws-sdk/s3-request-presigner"

const s3 = new S3Client({
  region: "auto",
  endpoint: `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: { 
    accessKeyId: process.env.R2_ACCESS_KEY, 
    secretAccessKey: process.env.R2_SECRET_KEY 
  }
})

export default async function handler(req, res){
  res.setHeader('Access-Control-Allow-Origin', '*');
  if(req.method==='OPTIONS') return res.status(200).end();

  const { filename, type } = req.query
  const key = `products/${Date.now()}-${filename}`

  const command = new PutObjectCommand({
    Bucket: "rekavo-images",
    Key: key,
    ContentType: type
  })

  const uploadUrl = await getSignedUrl(s3, command, { expiresIn: 120 })
  const publicUrl = `https://${process.env.R2_PUBLIC_DOMAIN}/${key}`

  res.json({ uploadUrl, publicUrl })
}
